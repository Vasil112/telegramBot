from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from bson import ObjectId
from datetime import datetime

from dotenv import load_dotenv
import os
load_dotenv()

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db = client['security']
users = db['users']
orders = db['orders']

def get_status_info(total_spent):
    """Повертає інформацію про статус на основі витраченої суми"""
    if total_spent >= 250000:
        return {"level": "diamond", "discount": 20, "threshold": 250000}
    elif total_spent >= 120000:
        return {"level": "gold", "discount": 10, "threshold": 120000}
    elif total_spent >= 50000:
        return {"level": "silver", "discount": 3, "threshold": 50000}
    elif total_spent > 0:
        return {"level": "bronze", "discount": 1, "threshold": 0}
    else:
        return {"level": "none", "discount": 0, "threshold": 0}

async def update_user_status(user_id):
    """Оновлює статус користувача на основі всіх його замовлень"""
    # Отримуємо всі замовлення користувача (враховуємо всі можливі статуси)
    user_orders = list(orders.find({
        "user_id": user_id,
        "status": {"$in": ["Оплачено", "Доставлено", "paid", "completed", "Нове", "В обробці", "Очікує оплати"]}
    }))
    
    # Рахуємо загальну суму витрат (враховуємо всі замовлення, крім скасованих)
    total_spent = sum(float(order.get('total_price', 0)) for order in user_orders 
                  if order.get('status') not in ["Скасовано", "canceled"])
    
    status_info = get_status_info(total_spent)
    
    # Оновлюємо запис користувача
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "status_user": total_spent,
            "user_status": status_info['level'],
            "user_discount": status_info['discount']
        }}
    )
    
    return status_info

async def show_status_info(update: Update, context: CallbackContext):
    """Показує інформацію про статус користувача"""
    user_id = update.effective_user.id
    user = users.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("Ви не зареєстровані в системі.")
        return
    
    # Оновлюємо статус перед показом
    status_info = await update_user_status(user_id)
    user = users.find_one({"user_id": user_id}) 
    
    # Визначаємо прогрес до наступного статусу
    next_status = None
    if status_info['level'] == "none":
        next_status = {"level": "bronze", "threshold": 0}
    elif status_info['level'] == "bronze":
        next_status = {"level": "silver", "threshold": 50000}
    elif status_info['level'] == "silver":
        next_status = {"level": "gold", "threshold": 120000}
    elif status_info['level'] == "gold":
        next_status = {"level": "diamond", "threshold": 250000}
    
    message = f"🌟 Ваш статус: {status_info['level'].capitalize()}\n"
    message += f"💎 Ваша знижка: {status_info['discount']}%\n"
    message += f"💰 Витрачено: {user.get('status_user', 0)} грн\n"
    
    if next_status:
        remaining = next_status['threshold'] - user.get('status_user', 0)
        if remaining > 0:
            message += f"\nДо наступного статусу ({next_status['level'].capitalize()}) залишилось: {remaining} грн"
        else:
            message += "\nВи досягли максимального статусу!"
    
    # Додаємо інформацію про бонуси
    message += "\n\n🔹 Бронзовий: 1% знижки (після першої покупки)\n"
    message += "🔸 Срібний: 3% знижки (від 50,000 грн)\n"
    message += "🔹 Золотий: 10% знижки (від 120,000 грн)\n"
    message += "💎 Діамантовий: 20% знижки (від 250,000 грн)"
    
    await update.message.reply_text(message)

def apply_discount(user_id, total_price):
    """Застосовує знижку до загальної суми замовлення на основі статусу"""
    user = users.find_one({"user_id": user_id})
    if not user:
        return total_price
    
    discount = user.get('user_discount', 0)
    if discount > 0:
        discounted_price = total_price * (1 - discount / 100)
        return round(discounted_price, 2)
    return total_price

async def update_status_after_purchase(user_id, order_amount, context: CallbackContext):
    status_info = await update_user_status(user_id)
    
    # Перевіряємо, чи отримано новий статус
    user = users.find_one({"user_id": user_id})
    if user and status_info['level'] != user.get('user_status', 'none'):
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 Вітаємо! Ви отримали {status_info['level'].capitalize()} статус!\n"
                 f"Тепер ваша знижка становить {status_info['discount']}%."
        )