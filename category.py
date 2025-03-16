from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from pymongo import MongoClient
from gridfs import GridFS
import io
from bson import ObjectId

# Підключення до MongoDB
client = MongoClient('mongodb://localhost:27017/')
db_goods = client['goods']  # База даних для товарів
fs = GridFS(db_goods)

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
        memory = specs.get('internal_memory', 'Немає інформації')  # Внутрішня пам'ять
        processor = specs.get('processor', 'Немає інформації')  # Процесор
        screen = specs.get('screen_type', 'Немає інформації')  # Тип екрану
        camera = specs.get('camera', 'Немає інформації')  #Камера
        number = product.get('number', 'Немає інформації')  # Кількість товару

        # Отримання зображення з GridFS
        image_id = product['photo_id']  # Переконайтеся, що поле називається 'photo_id'
        image = fs.get(ObjectId(image_id)).read()

        # Відправка зображення та інформації про товар
        caption = (
            f"📱 **{name}**\n\n"
            f"💰 Ціна: {price} грн\n\n"
            f"📜 Опис: {description}\n\n"
            f"💾 Пам'ять: {memory}\n"
            f"⚙️ Процесор: {processor}\n"
            f"🖥️ Екран: {screen}\n"
            f"📷 Камера: {camera}\n"
            f"📦 У наявності: {number} ✅"
        )

        await update.callback_query.message.reply_photo(photo=io.BytesIO(image), caption=caption)

        # Кнопки "Детальніше", "Придбати" та "До кошика"
        keyboard = [
            [InlineKeyboardButton("Детальніше", callback_data=f"detail_{product_id}"), InlineKeyboardButton("Придбати", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton("До кошика", callback_data=f"cart_{product_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("Оберіть дію:", reply_markup=reply_markup)

    # Кнопки "Назад" та "Далі" у новому форматі
    keyboard = []
    if page > 0:
        keyboard.append(InlineKeyboardButton("◀️ Назад", callback_data=f"prev_{category}"))
    keyboard.append(InlineKeyboardButton("Далі ▶️", callback_data=f"next_{category}"))
    reply_markup = InlineKeyboardMarkup([keyboard])
    await update.callback_query.message.reply_text("Навігація:", reply_markup=reply_markup)

async def button_callback(update: Update, context: CallbackContext, db_goods):  # Додано третій аргумент db_goods
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

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
        await show_product_details(update, context, product_id)
    elif data.startswith("buy_"):
        product_id = data.split("_")[1]
        await handle_buy_product(update, context, product_id)
    elif data.startswith("cart_"):
        product_id = data.split("_")[1]
        await handle_add_to_cart(update, context, product_id)
    else:
        # Якщо це не категорія, next_, prev_, detail_, buy_ чи cart_, ігноруємо
        pass

async def show_product_details(update: Update, context: CallbackContext, product_id: str):
    product = db_goods['products'].find_one({"_id": ObjectId(product_id)})
    if product:
        name = product['name']
        price = product['price']
        description = product['description']
        specs = product.get('specs', {})  # Отримуємо характеристики товару
        memory = specs.get('internal_memory', 'Немає інформації')  # Внутрішня пам'ять
        processor = specs.get('processor', 'Немає інформації')  # Процесор
        screen = specs.get('screen_type', 'Немає інформації')  # Тип екрану

        # Отримання зображення з GridFS
        image_id = product['image_id']
        image = fs.get(ObjectId(image_id)).read()

        # Відправка детальної інформації про товар
        caption = (
            f"**{name}**\n\n"
            f"Ціна: {price}\n"
            f"Опис: {description}\n"
            f"Пам'ять: {memory}\n"
            f"Процесор: {processor}\n"
            f"Екран: {screen}"
        )
        await update.callback_query.message.reply_photo(photo=io.BytesIO(image), caption=caption)

async def handle_buy_product(update: Update, context: CallbackContext, product_id: str):
    # Логіка для обробки покупки товару
    await update.callback_query.message.reply_text(f"Товар {product_id} додано до вашого замовлення.")

async def handle_add_to_cart(update: Update, context: CallbackContext, product_id: str):
    # Логіка для додавання товару до кошика
    await update.callback_query.message.reply_text(f"Товар {product_id} додано до кошика.")