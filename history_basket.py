from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db = client['security']
orders = db['orders']
users = db['users']

async def show_purchase_history(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_orders = list(orders.find({"user_id": user_id}).sort("order_date", -1))  # Сортуємо за датою (новіші першими)
    
    if not user_orders:
        await query.message.reply_text("У вас ще немає замовлень.")
        return
    
    # Обмежуємо кількість замовлень для відображення (наприклад, останні 10)
    user_orders = user_orders[:10]
    
    message = "📋 Ваша історія покупок:\n\n"
    
    for order in user_orders:
        order_date = order.get('order_date')
        if order_date:
            order_date_str = order_date.strftime("%d.%m.%Y %H:%M")
        else:
            order_date_str = "Невідома дата"
        
        message += f"🛒 Замовлення від {order_date_str}\n"
        message += f"🔢 Номер: {order.get('_id', 'Невідомо')}\n"
        message += f"💰 Сума: {order.get('total_price', 'Невідомо')} грн\n"
        message += f"📦 Кількість товарів: {len(order.get('items', []))}\n"
        message += f"📮 Статус: {order.get('status', 'Невідомо')}\n\n"

    
    await query.message.reply_text(message)

async def show_order_details(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    order_id = query.data.split("_")[-1]
    order = orders.find_one({"_id": ObjectId(order_id)})
    
    if not order:
        await query.message.reply_text("Замовлення не знайдено.")
        return
    
    message = f"📋 Деталі замовлення {order['_id']}:\n\n"
    message += f"📅 Дата: {order['order_date'].strftime('%d.%m.%Y %H:%M')}\n"
    message += f"👤 ПІБ: {order['full_name']}\n"
    message += f"📞 Телефон: {order['phone']}\n"
    message += f"🏠 Адреса: {order['address']}\n"
    message += f"💳 Спосіб оплати: {order['payment_method']}\n"
    message += f"💰 Початкова сума: {order['original_price']} грн\n"
    message += f"💎 Сума зі знижкою: {order['total_price']} грн\n"
    message += f"📮 Статус: {order.get('status', 'Невідомо')}\n\n"
    message += "📦 Товари:\n"
    
    for item in order['items']:
        message += f"- {item['product_name']} ({item['quantity']} шт.) - {item['price']} грн\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="purchase_history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(message, reply_markup=reply_markup)


def setup_handlers(application):
    application.add_handler(CallbackQueryHandler(show_purchase_history, pattern="^purchase_history$"))
    application.add_handler(CallbackQueryHandler(show_order_details, pattern="^order_details_"))