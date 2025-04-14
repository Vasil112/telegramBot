from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, MessageHandler, filters, CallbackQueryHandler
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
import io
import os
from dotenv import load_dotenv

load_dotenv()

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db_goods = client['goods']
fs = GridFS(db_goods)

async def show_search_button(update: Update, context: CallbackContext) -> None:
    """Показує кнопку пошуку поряд з категоріями"""
    keyboard = [
        [InlineKeyboardButton("🔍 Пошук товару", callback_data='search_product')],
        [InlineKeyboardButton("📱 Смартфони", callback_data='smartphones'),
         InlineKeyboardButton("📞 Телефони", callback_data='phones')],
        [InlineKeyboardButton("🍏 IPhone", callback_data='iphone'),
         InlineKeyboardButton("⌚ Годинники", callback_data='watches')],
        [InlineKeyboardButton("🎧 Аксесуари", callback_data='accessories')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Оберіть категорію або знайдіть товар:', reply_markup=reply_markup)

async def handle_search_callback(update: Update, context: CallbackContext) -> None:
    """Обробляє натискання кнопки пошуку"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'search_product':
        context.user_data['awaiting_search_query'] = True
        await query.message.reply_text("🔍 Введіть назву товару для пошуку:")

async def search_product(update: Update, context: CallbackContext) -> None:
    """Виконує пошук товару в базі даних"""
    if not context.user_data.get('awaiting_search_query'):
        return  # Якщо не очікуємо пошук, просто виходимо
    
    search_query = update.message.text.strip().lower()
    if not search_query:
        await update.message.reply_text("Будь ласка, введіть назву товару для пошуку.")
        return
    
    # Список категорій для пошуку
    categories = ['smartphones', 'phones', 'iphone', 'watches', 'accessories']
    found_products = []
    
    # Пошук по всіх категоріях
    for category in categories:
        products = db_goods[category].find({"name": {"$regex": search_query, "$options": "i"}})
        for product in products:
            product['category'] = category  # Додаємо категорію до продукту
            found_products.append(product)
    
    if not found_products:
        await update.message.reply_text(f"Товарів з назвою '{search_query}' не знайдено.")
        context.user_data.pop('awaiting_search_query', None)
        return
    
    # Відправляємо знайдені товари
    for product in found_products:
        name = product['name']
        price = product['price']
        description = product['description']
        category = product['category']
        specs = product.get('specs', {})
        quantity = product.get('quantity', 'Немає інформації')
        
        caption = (
            f"🔍 Знайдено в категорії '{category}':\n\n"
            f"📱 {name}\n\n"
            f"💰 Ціна: {price} грн\n\n"
            f"📜 Опис: {description}\n\n"
            f"📦 У наявності: {quantity} ✅"
        )
        
        # Додаємо характеристики, якщо вони є
        if specs:
            caption += "\n\nХарактеристики:\n"
            for key, value in specs.items():
                caption += f"• {key}: {value}\n"
        
        # Отримання зображення з GridFS
        if 'photo_id' in product:
            image_id = product['photo_id']
            image = fs.get(ObjectId(image_id)).read()
            
            keyboard = [
                [InlineKeyboardButton("Детальніше", callback_data=f"detail_{product['_id']}_{category}"),
                 InlineKeyboardButton("Придбати", callback_data=f"buy_{product['_id']}")],
                [InlineKeyboardButton("До кошика", callback_data=f"cart_{product['_id']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_photo(
                photo=io.BytesIO(image),
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(caption)
    
    context.user_data.pop('awaiting_search_query', None)

def setup_handlers_search(application):
    """Налаштовує обробники для пошуку"""
    application.add_handler(CallbackQueryHandler(handle_search_callback, pattern='^search_product$'))