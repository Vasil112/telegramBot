from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from pymongo import MongoClient
from gridfs import GridFS
import io
from bson import ObjectId
from basket import handle_add_to_cart

from dotenv import load_dotenv
import os
load_dotenv() 

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db_goods = client['goods']  
db_security = client['security']
fs = GridFS(db_goods)

async def show_product_details(update: Update, context: CallbackContext, product_id: str, category: str):
    product = db_goods[category].find_one({"_id": ObjectId(product_id)})
    if product:
        name = product.get('name', 'Немає інформації')
        price = product.get('price', 'Немає інформації')
        description = product.get('description', 'Немає інформації')
        quantity = product.get('quantity', 'Немає інформації')
        specs = product.get('specs', {})  

        # Формуємо основний опис товару з HTML-форматуванням
        caption = (
            f"<b>{name}</b>\n\n"
            f"💰 <b>Ціна:</b> {price} грн\n"
            f"📜 <b>Опис:</b> {description}\n"
            f"📦 <b>У наявності:</b> {quantity}\n\n"
        )

        if specs:
            caption += "<b>Характеристики:</b>\n"
            for key, value in specs.items():
                caption += f"• <b>{key}:</b> {value}\n"

        # Отримання зображення з GridFS
        image_id = product.get('photo_id')
        if image_id:
            try:
                image = fs.get(ObjectId(image_id)).read()
                await update.callback_query.message.reply_photo(photo=io.BytesIO(image))
            except Exception as e:
                print(f"Помилка при отриманні зображення: {e}")
                await update.callback_query.message.reply_text("Помилка при завантаженні зображення.")

        await update.callback_query.message.reply_text(caption, parse_mode="HTML")

        user_id = update.callback_query.from_user.id
        user = db_security.users.find_one({"user_id": user_id})
        user_status = user.get('status', 'pasive') if user else 'pasive'

        # Кнопки "До кошика" та "Придбати"
        if user_status == 'active':
            keyboard = [
                [InlineKeyboardButton("Придбати", callback_data=f"buy_{product_id}")],
                [InlineKeyboardButton("До кошика", callback_data=f"cart_{product_id}")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("Придбати", callback_data="not_active")],
                [InlineKeyboardButton("До кошика", callback_data="not_active")]
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("Оберіть дію:", reply_markup=reply_markup)

        if user_status != 'active':
            await update.callback_query.message.reply_text("Для виконання цієї операції спочатку потрібно створити акаунт.")
    else:
        await update.callback_query.message.reply_text("Товар не знайдено.")