from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, MessageHandler, filters
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import category
import basket
import account


import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db_security = client['security']
users = db_security['users']

async def show_main_keyboard(update: Update, context: CallbackContext) -> None:
    """Показує головну клавіатуру з основними кнопками"""
    user_id = update.message.from_user.id
    user = users.find_one({"user_id": user_id})
    
    # Якщо користувач є адміністратором, додаємо кнопку "Адміністрування"
    if user and user.get('access_level') == 'admin':
        keyboard = [
            ["📋 Каталог", "👤 Акаунт"],
            ["🛒 Кошик", "❓ Допомога"],
            ["🛑 СТОП", "⚙ Адміністрування"]
        ]
    else:
        keyboard = [
            ["📋 Каталог", "👤 Акаунт"],
            ["🛒 Кошик", "❓ Допомога"],
            ["🛑 СТОП"]
        ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Оберіть опцію:", reply_markup=reply_markup)

async def handle_keyboard_buttons(update: Update, context: CallbackContext) -> None:
    """Обробляє натискання кнопок головного меню"""
    logger.info(f"Отримано повідомлення: {update.message.text}")
    text = update.message.text
    
    if text == "📋 Каталог":
        logger.info("Обробка кнопки Каталог")
        await show_catalog(update, context)
    elif text == "👤 Акаунт":
        logger.info("Обробка кнопки Акаунт")
        await show_account_info(update, context)
    elif text == "🛒 Кошик":
        logger.info("Обробка кнопки Кошик")
        await show_basket(update, context)
    elif text == "❓ Допомога":
        logger.info("Обробка кнопки Допомога")
        await show_help(update, context)
    elif text == "🛑 СТОП":
        logger.info("Обробка кнопки СТОП")
        await stop_actions(update, context)
    elif text == "⚙ Адміністрування":
        logger.info("Обробка кнопки Адміністрування")
        await show_admin_panel(update, context)
    else:
        logger.warning(f"Невідома команда: {text}")

async def show_admin_panel(update: Update, context: CallbackContext) -> None:
    """Показує панель адміністратора"""
    # Використовуємо команду /status, яка вже реалізована для адміністраторів
    from bot import status
    await status(update, context)

async def show_catalog(update: Update, context: CallbackContext) -> None:
    """Показує каталог товарів"""
    keyboard = [
        [InlineKeyboardButton("📱 Смартфони", callback_data='smartphones')],
        [InlineKeyboardButton("📞 Телефони", callback_data='phones')],
        [InlineKeyboardButton("🍏 IPhone", callback_data='iphone')],
        [InlineKeyboardButton("⌚ Годинники", callback_data='watches')],
        [InlineKeyboardButton("🎧 Аксесуари", callback_data='accessories')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Оберіть категорію:', reply_markup=reply_markup)

async def show_account_info(update: Update, context: CallbackContext) -> None:
    """Показує інформацію про акаунт користувача"""
    await account.account(update, context)

async def show_basket(update: Update, context: CallbackContext) -> None:
    """Показує кошик користувача"""
    await basket.view_basket(update, context)

async def show_help(update: Update, context: CallbackContext) -> None:
    """Показує довідкову інформацію"""
    help_text = (
        "ℹ️ Довідка:\n\n"
        "📋 Каталог - перегляд доступних товарів\n"
        "👤 Акаунт - перегляд та редагування профілю\n"
        "🛒 Кошик - перегляд та оформлення замовлення\n"
        "🛑 СТОП - скасування поточних дій\n"
        "⚙ Адміністрування - панель управління для адміністраторів\n\n"
        "Для початку роботи використовуйте /start\n\n\n"
        "🛠️ Якщо у вас виникли проблеми, зверніться до адміністратора. @Vasil_112"
    )
    await update.message.reply_text(help_text)

async def stop_actions(update: Update, context: CallbackContext) -> None:
    """Скасовує поточні дії та очищає контекст"""
    context.user_data.clear()
    await update.message.reply_text(
        "Всі поточні дії скасовано. Ви можете почати знову."
    )
    await show_main_keyboard(update, context)  # Показуємо головну клавіатуру знову

def setup_handlers(application):
    """Додає обробники для клавіатурних кнопок"""
    application.add_handler(MessageHandler(
        filters.TEXT & (
            filters.Regex(r'^📋 Каталог$') |
            filters.Regex(r'^👤 Акаунт$') |
            filters.Regex(r'^🛒 Кошик$') |
            filters.Regex(r'^❓ Допомога$') |
            filters.Regex(r'^🛑 СТОП$') |
            filters.Regex(r'^⚙ Адміністрування$')
        ),
        handle_keyboard_buttons
    ))