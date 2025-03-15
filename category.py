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
        memory = product.get('memory', 'Немає інформації')  # Використовуємо .get() для безпеки
        processor = product.get('processor', 'Немає інформації')
        screen = product.get('screen', 'Немає інформації')

        # Отримання зображення з GridFS
        image_id = product['photo_id']  # Переконайтеся, що поле називається 'photo_id'
        image = fs.get(ObjectId(image_id)).read()

        # Відправка зображення та інформації про товар
        await update.callback_query.message.reply_photo(photo=io.BytesIO(image), caption=f"**{name}**\n\nЦіна: {price}\nОпис: {description}\nПам'ять: {memory}\nПроцесор: {processor}\nЕкран: {screen}")

        # Кнопка "Детальніше"
        keyboard = [[InlineKeyboardButton("Детальніше", callback_data=f"detail_{product_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("Детальніше:", reply_markup=reply_markup)

    # Кнопка "Далі"
    keyboard = [[InlineKeyboardButton("Далі", callback_data=f"next_{category}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Наступна сторінка:", reply_markup=reply_markup)

    
async def button_callback(update: Update, context: CallbackContext):
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
    elif data.startswith("detail_"):
        product_id = data.split("_")[1]
        await show_product_details(update, context, product_id)
    else:
        # Якщо це не категорія, next_ чи detail_, ігноруємо
        pass
            

async def show_product_details(update: Update, context: CallbackContext, product_id: str):
    product = db_goods['products'].find_one({"_id": ObjectId(product_id)})
    if product:
        name = product['name']
        price = product['price']
        description = product['description']
        memory = product['memory']
        processor = product['processor']
        screen = product['screen']

        # Отримання зображення з GridFS
        image_id = product['image_id']
        image = fs.get(ObjectId(image_id)).read()

        # Відправка детальної інформації про товар
        await update.callback_query.message.reply_photo(photo=io.BytesIO(image), caption=f"**{name}**\n\nЦіна: {price}\nОпис: {description}\nПам'ять: {memory}\nПроцесор: {processor}\nЕкран: {screen}")

# Додайте ці обробники до основного коду в bot.py