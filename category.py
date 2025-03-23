import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from pymongo import MongoClient
from gridfs import GridFS
import io
from bson import ObjectId
import details
from basket import handle_add_to_cart

# Підключення до MongoDB
client = MongoClient('mongodb://localhost:27017/')
db_goods = client['goods']  # База даних для товарів
fs = GridFS(db_goods)
db_security = client['security']

# Змінна для зберігання поточної сторінки
current_page = {}

async def show_category(update: Update, context: CallbackContext, category: str):
    user_id = update.callback_query.from_user.id
    current_page[user_id] = 0  # Починаємо з першої сторінки

    await display_products(update, context, category, user_id)

async def display_products(update: Update, context: CallbackContext, category: str, user_id: int):
    page = current_page.get(user_id, 0)
    products = list(db_goods[category].find().skip(page * 5).limit(5))

    if not products:
        await update.callback_query.message.reply_text("Товари в цій категорії закінчилися.")
        return

    for product in products:
        product_id = product['_id']
        name = product['name']
        price = product['price']
        description = product['description']
        specs = product.get('specs', {})  # Отримуємо характеристики товару
        number = product.get('quantity', 'Немає інформації')  # Кількість у наявності

        # Визначаємо, які характеристики відображати в залежності від категорії
        if category == "smartphones":
            memory = specs.get('Внутрішня пам\'ять', 'Немає інформації')
            processor = specs.get('Процесор', 'Немає інформації')
            screen = specs.get('Тип екрану', 'Немає інформації')
            camera = specs.get('Камера', 'Немає інформації')

            # Формуємо підпис для смартфонів
            caption = (
                f"📱 {name}\n\n"
                f"💰 Ціна: {price} грн\n\n"
                f"📜 Опис: {description}\n\n"
                f"💾 Пам'ять: {memory}\n"
                f"⚙️ Процесор: {processor}\n"
                f"🖥️ Екран: {screen}\n"
                f"📷 Камера: {camera}\n"
                f"📦 У наявності: {number} ✅"
            )
        elif category == "phones":
            memory = specs.get('Внутрішня пам\'ять', 'Немає інформації')
            camera = specs.get('Камера', 'Немає інформації')
            bluetooth = specs.get('Bluetooth', 'Немає інформації')

            # Формуємо підпис для телефонів
            caption = (
                f"📱 {name}\n\n"
                f"💰 Ціна: {price} грн\n\n"
                f"📜 Опис: {description}\n\n"
                f"💾 Пам'ять: {memory}\n"
                f"📷 Камера: {camera}\n"
                f"📶 Bluetooth: {bluetooth}\n"
                f"📦 У наявності: {number} ✅"
            )
        elif category == "iphone":
            memory = specs.get('Внутрішня пам\'ять', 'Немає інформації')
            processor = specs.get('Процесор', 'Немає інформації')
            screen = specs.get('Тип екрану', 'Немає інформації')
            camera = specs.get('Камера', 'Немає інформації')

            caption = (
                f"📱 {name}\n\n"
                f"💰 Ціна: {price} грн\n\n"
                f"📜 Опис: {description}\n\n"
                f"💾 Пам'ять: {memory}\n"
                f"⚙️ Процесор: {processor}\n"
                f"🖥️ Екран: {screen}\n"
                f"📷 Камера: {camera}\n"
                f"📦 У наявності: {number} ✅"
            )
        else:
            # Для інших категорій (iphone, watches, accessories) відображаємо лише основні дані
            caption = (
                f"📱 {name}\n\n"
                f"💰 Ціна: {price} грн\n\n"
                f"📜 Опис: {description}\n\n"
                f"📦 У наявності: {number} ✅"
            )

        # Отримання зображення з GridFS
        image_id = product['photo_id']  # Переконайтеся, що поле називається 'photo_id'
        image = fs.get(ObjectId(image_id)).read()

        # Відправка зображення та інформації про товар
        await update.callback_query.message.reply_photo(photo=io.BytesIO(image), caption=caption)

        # Кнопки "Детальніше", "Придбати" та "До кошика" для кожного товару
        keyboard = [
            [InlineKeyboardButton("Детальніше", callback_data=f"detail_{product_id}_{category}"),
             InlineKeyboardButton("Придбати", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton("До кошика", callback_data=f"cart_{product_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("Оберіть дію:", reply_markup=reply_markup)

    # Кнопки "Назад" та "Далі" для навігації по сторінках
    keyboard = []
    if page > 0:
        keyboard.append(InlineKeyboardButton("◀️ Назад", callback_data=f"prev_{category}"))
    keyboard.append(InlineKeyboardButton("Далі ▶️", callback_data=f"next_{category}"))
    reply_markup = InlineKeyboardMarkup([keyboard])
    await update.callback_query.message.reply_text("Навігація:", reply_markup=reply_markup)

async def handle_category_callback(update: Update, context: CallbackContext, db_goods):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Отримуємо статус користувача
    user = db_security.users.find_one({"user_id": user_id})
    user_status = user.get('status', 'pasive') if user else 'pasive'

    # Перевіряємо, чи callback_data стосується категорій
    if data in ["accessories", "iphone", "phones", "smartphones", "watches"]:
        await show_category(update, context, data)
    elif data.startswith("next_"):
        category = data.split("_")[1]
        current_page[user_id] += 1
        await display_products(update, context, category, user_id)
    elif data.startswith("prev_"):
        category = data.split("_")[1]
        current_page[user_id] -= 1
        await display_products(update, context, category, user_id)
    elif data.startswith("detail_"):
        product_id = data.split("_")[1]
        category = data.split("_")[2]  # Отримуємо категорію з callback_data
        await details.show_product_details(update, context, product_id, category)
    elif data.startswith("buy_"):
        if user_status == 'active':
            product_id = data.split("_")[1]
            await handle_buy_product(update, context, product_id)
        else:
            await query.message.reply_text("Для виконання цієї операції спочатку потрібно створити акаунт.")
    elif data.startswith("cart_"):
        if user_status == 'active':
            product_id = data.split("_")[1]
            await handle_add_to_cart(update, context, product_id)
        else:
            await query.message.reply_text("Для виконання цієї операції спочатку потрібно створити акаунт.")
    else:
        # Якщо це не категорія, next_, prev_, detail_, buy_ чи cart_, ігноруємо
        pass

async def handle_buy_product(update: Update, context: CallbackContext, product_id: str):
    # Логіка для обробки покупки товару
    await update.callback_query.message.reply_text(f"Товар {product_id} додано до вашого замовлення.")

