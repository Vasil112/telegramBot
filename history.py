from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, MessageHandler, filters, CallbackQueryHandler
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime

# Підключення до MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['security']
orders = db['orders']
basket = db['basket']
users = db['users']

async def confirm_final_order(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    # Запитуємо адресу
    await query.message.reply_text("Введіть адресу замовлення (наприклад: місто Київ, вулиця Богдана Хмельницького 57, Нова пошта відділення №1):")
    
    # Зберігаємо стан для наступного кроку
    context.user_data['order_flow'] = 'awaiting_address'

async def handle_address(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('order_flow') != 'awaiting_address':
        return
    
    address = update.message.text
    context.user_data['order_address'] = address
    
    # Запитуємо ПІБ
    await update.message.reply_text("Введіть Ваш ПІБ:")
    context.user_data['order_flow'] = 'awaiting_name'

async def handle_name(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('order_flow') != 'awaiting_name':
        return
    
    full_name = update.message.text
    context.user_data['order_name'] = full_name
    
    # Запитуємо спосіб оплати
    keyboard = [
        [InlineKeyboardButton("Передоплата", callback_data="payment_prepay")],
        [InlineKeyboardButton("При отриманні", callback_data="payment_cod")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Оберіть спосіб оплати:",
        reply_markup=reply_markup
    )
    context.user_data['order_flow'] = 'awaiting_payment'

async def handle_payment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if context.user_data.get('order_flow') != 'awaiting_payment':
        return
    
    payment_method = "Передоплата" if query.data == "payment_prepay" else "При отриманні"
    
    # Отримуємо всі дані
    user_id = query.from_user.id
    address = context.user_data.get('order_address', 'Не вказано')
    full_name = context.user_data.get('order_name', 'Не вказано')
    
    # Отримуємо товари з кошика
    basket_items = list(basket.find({"user_id": user_id}))
    
    # Розраховуємо загальну суму
    total_price = sum(int(item['price']) * item['quantity'] for item in basket_items)
    
    # Створюємо запис про замовлення
    order_data = {
        "user_id": user_id,
        "items": basket_items,
        "total_price": total_price,
        "address": address,
        "full_name": full_name,
        "payment_method": payment_method,
        "status": "Нове",
        "order_date": datetime.now()
    }
    orders.insert_one(order_data)
    
    # Очищаємо кошик
    basket.delete_many({"user_id": user_id})
    
    # Оновлюємо кількість товарів у кошику користувача
    users.update_one({"user_id": user_id}, {"$set": {"basket": 0}})
    
    # Надсилаємо фінальне повідомлення
    await query.message.reply_text(
        "Чудово! Замовлення оформлене.\n\n"
        f"Деталі замовлення:\n"
        f"ПІБ: {full_name}\n"
        f"Адреса: {address}\n"
        f"Спосіб оплати: {payment_method}\n"
        f"Загальна сума: {total_price} грн\n\n"
        "На вашу пошту надіслано квитанцію про покупку."
    )
    
    # Очищаємо дані про замовлення
    context.user_data.clear()

def setup_handlers(application):
    # Додаємо обробники для кожної стадії оформлення
    application.add_handler(CallbackQueryHandler(confirm_final_order, pattern="^confirm_final_order$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern="^payment_"))