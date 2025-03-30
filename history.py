from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, MessageHandler, filters, CallbackQueryHandler
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import re
from oplata import handle_monobank_payment
import spam
import bonus

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
        address_data = user_addresses.find_one({"_id": ObjectId(address_id)})
        if address_data:
            # Зберігаємо адресу
            context.user_data['order_address'] = address_data['address']
            
            # Якщо в базі вже є ПІБ і телефон, пропонуємо їх використати
            if address_data.get('full_name') and address_data.get('phone'):
                keyboard = [
                    [InlineKeyboardButton("✅ Використати збережені дані", callback_data="use_saved_data_yes")],
                    [InlineKeyboardButton("❌ Ввести нові дані", callback_data="use_saved_data_no")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    f"Використати збережені дані?\nПІБ: {address_data['full_name']}\nТелефон: {address_data['phone']}",
                    reply_markup=reply_markup
                )
                context.user_data['awaiting_data_decision'] = True
                # Зберігаємо дані на випадок, якщо користувач обере "Використати"
                context.user_data['saved_full_name'] = address_data['full_name']
                context.user_data['saved_phone'] = address_data['phone']
            else:
                await ask_for_full_name(update, context)
    except Exception as e:
        print(f"Помилка при обробці адреси: {e}")
        await query.message.reply_text("Сталася помилка при обробці адреси. Спробуйте ще раз.")

async def handle_use_saved_data_decision(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data == "use_saved_data_yes":
        # Використовуємо збережені дані
        context.user_data['order_full_name'] = context.user_data.get('saved_full_name', '')
        context.user_data['order_phone'] = context.user_data.get('saved_phone', '')
        # Видаляємо тимчасові дані
        if 'saved_full_name' in context.user_data:
            del context.user_data['saved_full_name']
        if 'saved_phone' in context.user_data:
            del context.user_data['saved_phone']
    else:
        await ask_for_full_name(update, context)
    
    del context.user_data['awaiting_data_decision']
    await ask_for_payment_method(update, context)


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
    basket_items = list(basket.find({"user_id": user_id}))
    
    if not basket_items:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Ваш кошик порожній!"
        )
        return
    
    # Оновлюємо кількість товарів у базі даних
    client = MongoClient(os.getenv("MONGO_URI"))
    db_goods = client['goods']
    
    for item in basket_items:
        # Пропускаємо товари з is_protection=True
        if item.get('is_protection', False):
            continue
            
        # Додаємо перевірку на наявність обов'язкових полів
        if 'category' not in item or 'product_id' not in item:
            continue
            
        category_name = item['category']
        product_id = item['product_id']
        
        # Оновлюємо кількість товару
        db_goods[category_name].update_one(
            {"_id": ObjectId(product_id)},
            {"$inc": {"quantity": -int(item.get('quantity', 1))}}
        )
    
    order_data = {
        "user_id": user_id,
        "items": basket_items,
        "address": context.user_data.get('order_address', ''),
        "full_name": context.user_data.get('order_full_name', ''),
        "phone": context.user_data.get('order_phone', ''),
        "payment_method": context.user_data.get('payment_method', ''),
        "status": "Нове",
        "order_date": datetime.now()
    }
    
    # Розраховуємо загальну суму
    total_price = sum(float(item['price']) * int(item.get('quantity', 1)) for item in order_data['items'])
    order_data['total_price'] = total_price
    
    # Зберігаємо замовлення
    order = orders.insert_one(order_data)
    order_id = order.inserted_id
    
    # Очищаємо кошик
    basket.delete_many({"user_id": user_id})
    
    # Надсилаємо підтвердження в чат
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
    
    # Надсилаємо лист з підтвердженням на пошту
    user = users.find_one({"user_id": user_id})
    if user and user.get('email'):
        try:
            await spam.send_order_confirmation(update, context, order_id)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📧 Лист з підтвердженням замовлення було надіслано на {user['email']}"
            )
        except Exception as e:
            print(f"Помилка при відправці листа: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Не вдалося надіслати лист з підтвердженням. Будь ласка, перевірте ваш email у профілі."
            )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ Email не вказано в профілі. Лист з підтвердженням не було надіслано."
        )
    
    # Очищаємо тимчасові дані
    context.user_data.clear()
    await bonus.update_status_after_purchase(user_id, total_price, context)



def setup_handlers(application):
    # Обробники кнопок
    application.add_handler(CallbackQueryHandler(confirm_final_order, pattern="^confirm_final_order$"))
    application.add_handler(CallbackQueryHandler(handle_address_selection, pattern="^select_address_|^add_new_address$"))
    application.add_handler(CallbackQueryHandler(handle_use_saved_data_decision, pattern="^use_saved_data_"))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern="^payment_"))
    
    # Обробники повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^[А-ЯҐЄІЇ][а-яґєії]+\s[А-ЯҐЄІЇ][а-яґєії]+\s[А-ЯҐЄІЇ][а-яґєії]+$'), handle_full_name))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\+380\d{9}$'), handle_phone_number))
