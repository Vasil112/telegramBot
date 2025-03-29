from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, filters
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import re
import history  # Додати на початку файлу
from dotenv import load_dotenv
import os
load_dotenv()

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db = client['security']
user_addresses = db['user_addresses']

async def handle_manage_address(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    addresses = list(user_addresses.find({"user_id": user_id}))
    
    if addresses:
        message = "Ваші збережені адреси:\n\n" + "\n".join([f"📍 {addr['address']}" for addr in addresses])
        keyboard = [
            [InlineKeyboardButton("Додати нову адресу", callback_data="add_new_address")],
            [InlineKeyboardButton("Видалити адресу", callback_data="delete_address")]
        ]
    else:
        message = "У вас немає збережених адрес."
        keyboard = [[InlineKeyboardButton("Додати адресу", callback_data="add_new_address")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(message, reply_markup=reply_markup)

async def handle_delete_address(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    addresses = list(user_addresses.find({"user_id": user_id}))
    
    if not addresses:
        await query.message.reply_text("У вас немає збережених адрес для видалення.")
        return
    
    keyboard = [
        [InlineKeyboardButton(addr['address'], callback_data=f"delete_address_{str(addr['_id'])}")]
        for addr in addresses
    ]
    keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="manage_address")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Оберіть адресу для видалення:", reply_markup=reply_markup)

async def confirm_delete_address(update: Update, context: CallbackContext, address_id: str) -> None:
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Так, видалити", callback_data=f"confirm_delete_addr_{address_id}")],
        [InlineKeyboardButton("❌ Ні, скасувати", callback_data="manage_address")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text("Ви впевнені, що хочете видалити цю адресу?", reply_markup=reply_markup)

async def delete_address(update: Update, context: CallbackContext, address_id: str) -> None:
    query = update.callback_query
    await query.answer()
    
    try:
        result = user_addresses.delete_one({"_id": ObjectId(address_id)})
        
        if result.deleted_count > 0:
            await query.message.reply_text("✅ Адресу успішно видалено!")
        else:
            await query.message.reply_text("❌ Не вдалося знайти адресу для видалення.")
    except Exception as e:
        print(f"Помилка при видаленні адреси: {e}")
        await query.message.reply_text("❌ Сталася помилка при видаленні адреси.")
    
    await handle_manage_address(update, context)

async def handle_address(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get('awaiting_address'):
        return
    
    address = update.message.text.strip()
    if not address:
        await update.message.reply_text("Будь ласка, введіть коректну адресу")
        return
    
    context.user_data['order_address'] = address
    del context.user_data['awaiting_address']
    
    keyboard = [
        [InlineKeyboardButton("✅ Так, зберегти", callback_data="save_address_yes")],
        [InlineKeyboardButton("❌ Ні, не зберігати", callback_data="save_address_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Бажаєте зберегти цю адресу разом з вашими даними для майбутніх замовлень?", reply_markup=reply_markup)
    context.user_data['awaiting_address_save'] = True

async def handle_address_save_decision(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if not context.user_data.get('awaiting_address_save'):
        return
    
    user_id = query.from_user.id
    address = context.user_data.get('order_address', '')
    
    if query.data == "save_address_yes":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Для збереження адреси введіть Ваш ПІБ у форматі: Прізвище Ім'я По-батькові (наприклад: Іванов Іван Іванович):"
        )
        context.user_data['awaiting_full_name_for_save'] = True
        context.user_data['address_to_save'] = address
    else:
        del context.user_data['awaiting_address_save']
        await history.ask_for_full_name(update, context)

async def handle_full_name_for_save(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get('awaiting_full_name_for_save'):
        return
    
    full_name = update.message.text.strip()
    if not re.match(r'^[А-ЯҐЄІЇ][а-яґєії]+\s[А-ЯҐЄІЇ][а-яґєії]+\s[А-ЯҐЄІЇ][а-яґєії]+$', full_name):
        await update.message.reply_text("Будь ласка, введіть ПІБ у правильному форматі: Прізвище Ім'я По-батькові")
        return
    
    context.user_data['full_name_to_save'] = full_name
    del context.user_data['awaiting_full_name_for_save']
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Введіть Ваш номер телефону у форматі +380XXXXXXXXX для збереження:"
    )
    context.user_data['awaiting_phone_for_save'] = True

async def handle_phone_for_save(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get('awaiting_phone_for_save'):
        return
    
    phone = update.message.text.strip()
    if not re.match(r'^\+380\d{9}$', phone):
        await update.message.reply_text("Будь ласка, введіть номер у форматі +380XXXXXXXXX")
        return
    
    full_name = context.user_data.get('full_name_to_save', '')
    address = context.user_data.get('address_to_save', '')
    
    user_addresses.insert_one({
        "user_id": update.effective_user.id,
        "address": address,
        "full_name": full_name,
        "phone": phone,
        "created_at": datetime.now()
    })
    
    await update.message.reply_text("✅ Адресу та ваші дані збережено!")
    
    context.user_data['order_full_name'] = full_name
    context.user_data['order_phone'] = phone
    
    keys_to_delete = [
        'awaiting_phone_for_save',
        'address_to_save',
        'full_name_to_save',
        'awaiting_address_save'
    ]
    for key in keys_to_delete:
        if key in context.user_data:
            del context.user_data[key]
    
    await history.ask_for_payment_method(update, context)

def setup_handlers(application):
    application.add_handler(CallbackQueryHandler(handle_manage_address, pattern="^manage_address$"))
    application.add_handler(CallbackQueryHandler(handle_delete_address, pattern="^delete_address$"))
    application.add_handler(CallbackQueryHandler(confirm_delete_address, pattern="^delete_address_"))  
    application.add_handler(CallbackQueryHandler(delete_address, pattern="^confirm_delete_addr_"))
    application.add_handler(CallbackQueryHandler(handle_address_save_decision, pattern="^save_address_"))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_full_name_for_save))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\+380\d{9}$'), handle_phone_for_save))