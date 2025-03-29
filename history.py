from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, MessageHandler, filters, CallbackQueryHandler
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import re
from oplata import handle_monobank_payment
import address

from dotenv import load_dotenv
import os
load_dotenv()  # Завантажує змінні з .env

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db = client['security']
orders = db['orders']
basket = db['basket']
users = db['users']
user_addresses = db['user_addresses']

async def confirm_final_order(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    addresses = list(user_addresses.find({"user_id": user_id}))
    
    if addresses:
        keyboard = [
            [InlineKeyboardButton(addr['address'], callback_data=f"select_address_{str(addr['_id'])}")]
            for addr in addresses
        ]
        keyboard.append([InlineKeyboardButton("➕ Додати нову адресу", callback_data="add_new_address")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Оберіть адресу доставки:", reply_markup=reply_markup)
    else:
        await query.message.reply_text("Введіть адресу замовлення (наприклад: місто Київ, вулиця Богдана Хмельницького 57, Нова пошта відділення №1):")
        context.user_data['awaiting_address'] = True

async def handle_address_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_new_address":
        await query.message.reply_text("Введіть нову адресу доставки:")
        context.user_data['awaiting_address'] = True
        return
    
    try:
        address_id = query.data.split("_")[-1]
        address = user_addresses.find_one({"_id": ObjectId(address_id)})
        if address:
            context.user_data['order_address'] = address['address']
            context.user_data['order_full_name'] = address.get('full_name', '')
            context.user_data['order_phone'] = address.get('phone', '')
            
            # Якщо в базі вже є ПІБ і телефон, пропонуємо їх використати
            if address.get('full_name') and address.get('phone'):
                keyboard = [
                    [InlineKeyboardButton("✅ Використати збережені дані", callback_data="use_saved_data_yes")],
                    [InlineKeyboardButton("❌ Ввести нові дані", callback_data="use_saved_data_no")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    f"Використати збережені дані?\nПІБ: {address['full_name']}\nТелефон: {address['phone']}",
                    reply_markup=reply_markup
                )
                context.user_data['awaiting_data_decision'] = True
            else:
                await ask_for_full_name(update, context)
    except Exception as e:
        print(f"Помилка при обробці адреси: {e}")
        await query.message.reply_text("Сталася помилка при обробці адреси. Спробуйте ще раз.")

async def handle_use_saved_data_decision(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data == "use_saved_data_yes":
        await ask_for_payment_method(update, context)
    else:
        await ask_for_full_name(update, context)
    
    del context.user_data['awaiting_data_decision']


async def ask_for_full_name(update: Update, context: CallbackContext) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Введіть Ваш ПІБ у форматі: Прізвище Ім'я По-батькові (наприклад: Іванов Іван Іванович):"
    )
    context.user_data['awaiting_full_name'] = True

async def handle_full_name(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get('awaiting_full_name'):
        return
    
    full_name = update.message.text.strip()
    if not re.match(r'^[А-ЯҐЄІЇ][а-яґєії]+\s[А-ЯҐЄІЇ][а-яґєії]+\s[А-ЯҐЄІЇ][а-яґєії]+$', full_name):
        await update.message.reply_text("Будь ласка, введіть ПІБ у правильному форматі: Прізвище Ім'я По-батькові")
        return
    
    context.user_data['order_full_name'] = full_name
    del context.user_data['awaiting_full_name']
    await ask_for_phone_number(update, context)

async def ask_for_phone_number(update: Update, context: CallbackContext) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Введіть Ваш номер телефону у форматі +380XXXXXXXXX:"
    )
    context.user_data['awaiting_phone'] = True

async def handle_phone_number(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get('awaiting_phone'):
        return
    
    phone = update.message.text.strip()
    if not re.match(r'^\+380\d{9}$', phone):
        await update.message.reply_text("Будь ласка, введіть номер у форматі +380XXXXXXXXX")
        return
    
    context.user_data['order_phone'] = phone
    del context.user_data['awaiting_phone']
    await ask_for_payment_method(update, context)

async def ask_for_payment_method(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Передоплата", callback_data="payment_prepay")],
        [InlineKeyboardButton("Оплата при отриманні", callback_data="payment_cod")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Оберіть спосіб оплати:",
        reply_markup=reply_markup
    )
    context.user_data['awaiting_payment'] = True

async def handle_payment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if not context.user_data.get('awaiting_payment'):
        return
    
    payment_method = query.data
    context.user_data['payment_method'] = "Передоплата" if payment_method == "payment_prepay" else "Оплата при отриманні"
    del context.user_data['awaiting_payment']
    
    if payment_method == "payment_prepay":
        # Для передоплати - переходимо до процесу оплати
        await handle_monobank_payment(update, context)
    else:
        # Для оплати при отриманні - завершуємо замовлення
        await complete_order(update, context)

async def complete_order(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    order_data = {
        "user_id": user_id,
        "items": list(basket.find({"user_id": user_id})),
        "address": context.user_data.get('order_address', ''),
        "full_name": context.user_data.get('order_full_name', ''),
        "phone": context.user_data.get('order_phone', ''),
        "payment_method": context.user_data.get('payment_method', ''),
        "status": "Нове",
        "order_date": datetime.now()
    }
    
    # Розраховуємо загальну суму
    total_price = sum(float(item['price']) * int(item['quantity']) for item in order_data['items'])
    order_data['total_price'] = total_price
    
    # Зберігаємо замовлення
    orders.insert_one(order_data)
    
    # Очищаємо кошик
    basket.delete_many({"user_id": user_id})
    
    # Надсилаємо підтвердження
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"""✅ Замовлення оформлено!
        
📋 Деталі замовлення:
👤 ПІБ: {order_data['full_name']}
📞 Телефон: {order_data['phone']}
🏠 Адреса: {order_data['address']}
💳 Спосіб оплати: {order_data['payment_method']}
💰 Загальна сума: {total_price} грн

Дякуємо за замовлення!"""
    )
    
    # Очищаємо тимчасові дані
    context.user_data.clear()

def setup_handlers(application):
    # Обробники кнопок
    application.add_handler(CallbackQueryHandler(confirm_final_order, pattern="^confirm_final_order$"))
    application.add_handler(CallbackQueryHandler(handle_address_selection, pattern="^select_address_|^add_new_address$"))
    application.add_handler(CallbackQueryHandler(handle_use_saved_data_decision, pattern="^use_saved_data_"))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern="^payment_"))
    
    # Обробники повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^[А-ЯҐЄІЇ][а-яґєії]+\s[А-ЯҐЄІЇ][а-яґєії]+\s[А-ЯҐЄІЇ][а-яґєії]+$'), handle_full_name))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\+380\d{9}$'), handle_phone_number))
