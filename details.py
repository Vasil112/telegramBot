from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from pymongo import MongoClient
from gridfs import GridFS
import io
from bson import ObjectId
from basket import handle_add_to_cart

# Підключення до MongoDB
client = MongoClient('mongodb://localhost:27017/')
db_goods = client['goods']  # База даних для товарів
fs = GridFS(db_goods)

async def show_product_details(update: Update, context: CallbackContext, product_id: str, category: str):
    # Отримуємо товар з відповідної колекції категорії
    product = db_goods[category].find_one({"_id": ObjectId(product_id)})
    if product:
        name = product.get('name', 'Немає інформації')
        price = product.get('price', 'Немає інформації')
        description = product.get('description', 'Немає інформації')
        quantity = product.get('quantity', 'Немає інформації')
        specs = product.get('specs', {})  # Отримуємо характеристики товару

        # Формуємо основний опис товару з HTML-форматуванням
        caption = (
            f"<b>{name}</b>\n\n"
            f"💰 <b>Ціна:</b> {price} грн\n"
            f"📜 <b>Опис:</b> {description}\n"
            f"📦 <b>У наявності:</b> {quantity}\n\n"
        )

        # Додаємо всі характеристики зі specs
        if specs:
            caption += "<b>Характеристики:</b>\n"
            for key, value in specs.items():
                caption += f"• <b>{key}:</b> {value}\n"

        # Отримання зображення з GridFS
        image_id = product.get('photo_id')
        if image_id:
            try:
                image = fs.get(ObjectId(image_id)).read()
                # Відправка зображення
                await update.callback_query.message.reply_photo(photo=io.BytesIO(image))
            except Exception as e:
                print(f"Помилка при отриманні зображення: {e}")
                await update.callback_query.message.reply_text("Помилка при завантаженні зображення.")

        # Відправка текстового опису з підтримкою HTML-розмітки
        await update.callback_query.message.reply_text(caption, parse_mode="HTML")

        # Кнопки "До кошика" та "Придбати"
        keyboard = [
            [InlineKeyboardButton("Придбати", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton("До кошика", callback_data=f"cart_{product_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("Оберіть дію:", reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text("Товар не знайдено.")
