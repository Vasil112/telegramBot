from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, MessageHandler, filters, CallbackQueryHandler
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import logging

# Налаштування логування
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
products_db = client['goods']

async def show_main_keyboard(update: Update, context: CallbackContext) -> None:
    """Показує головну клавіатуру"""
    user_id = update.message.from_user.id
    user = users.find_one({"user_id": user_id})
    
    keyboard = [
        ["📋 Каталог", "👤 Акаунт"],
        ["🛒 Кошик", "❓ Допомога"],
        ["🛑 СТОП"] + (["⚙ Адміністрування"] if user and user.get('access_level') == 'admin' else [])
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Оберіть опцію:", reply_markup=reply_markup)

async def show_admin_keyboard(update: Update, context: CallbackContext) -> None:
    """Показує клавіатуру адміністратора"""
    keyboard = [
        ["📦 Товари", "👥 Користувачі"],
        ["🆘 Допомога", "🔙 Назад"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Адміністративне меню:", reply_markup=reply_markup)

async def stop_actions(update: Update, context: CallbackContext) -> None:
    """Скасовує поточні дії"""
    context.user_data.clear()
    await update.message.reply_text("Всі дії скасовано. Головне меню:")
    await show_main_keyboard(update, context)

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
    """Показує інформацію про акаунт"""
    from account import account
    await account(update, context)

async def show_basket(update: Update, context: CallbackContext) -> None:
    """Показує кошик користувача"""
    from basket import view_basket
    await view_basket(update, context)

async def show_help(update: Update, context: CallbackContext) -> None:
    """Показує довідкову інформацію"""
    help_text = (
        "ℹ️ Довідка:\n\n"
        "📋 Каталог - перегляд товарів\n"
        "👤 Акаунт - управління профілем\n"
        "🛒 Кошик - перегляд кошика\n"
        "🛑 СТОП - скасування дій\n"
        "⚙ Адміністрування - панель адміністратора"
    )
    await update.message.reply_text(help_text)

async def show_admin_products(update: Update, context: CallbackContext) -> None:
    """Меню управління товарами"""
    keyboard = [
        [InlineKeyboardButton("Додати товар", callback_data='add_product')],
        [InlineKeyboardButton("Видалити товар", callback_data='delete_product')],
        [InlineKeyboardButton("Редагувати товар", callback_data='edit_product')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text("Управління товарами:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Управління товарами:", reply_markup=reply_markup)


async def show_admin_users(update: Update, context: CallbackContext) -> None:
    """Меню управління користувачами"""
    keyboard = [
        [InlineKeyboardButton("Список користувачів", callback_data='list_users')],
        [InlineKeyboardButton("Змінити статус", callback_data='change_status')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Управління користувачами:", reply_markup=reply_markup)

async def show_admin_help(update: Update, context: CallbackContext) -> None:
    """Довідка для адміністратора"""
    help_text = (
        "🆘 Адмін-довідка:\n\n"
        "📦 Товари - додавання/редагування товарів\n"
        "👥 Користувачі - управління користувачами\n"
        "🔙 Назад - повернення до меню"
    )
    await update.message.reply_text(help_text)

async def handle_keyboard_buttons(update: Update, context: CallbackContext) -> None:
    """Обробляє натискання кнопок головного меню"""
    text = update.message.text
    
    if text == "📋 Каталог":
        await show_catalog(update, context)
    elif text == "👤 Акаунт":
        await show_account_info(update, context)
    elif text == "🛒 Кошик":
        await show_basket(update, context)
    elif text == "❓ Допомога":
        await show_help(update, context)
    elif text == "🛑 СТОП":
        await stop_actions(update, context)
    elif text == "⚙ Адміністрування":
        await show_admin_keyboard(update, context)
    elif text == "📦 Товари":
        await show_admin_products(update, context)
    elif text == "👥 Користувачі":
        await show_admin_users(update, context)
    elif text == "🆘 Допомога":
        await show_admin_help(update, context)
    elif text == "🔙 Назад":
        await show_main_keyboard(update, context)
    else:
        await update.message.reply_text("Невідома команда. Спробуйте ще раз.")

async def handle_admin_buttons(update: Update, context: CallbackContext) -> None:
    """Обробка кнопок адміністратора"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'admin_back':
        await query.edit_message_text("Повернення до адмін-меню...")
        await show_admin_keyboard(update, context)
    elif query.data == 'add_product':
        await handle_add_product(update, context)
    elif query.data == 'delete_product':
        await handle_delete_product(update, context)
    elif query.data == 'edit_product':
        await handle_edit_product(update, context)
    elif query.data == 'list_users':
        await handle_list_users(update, context)
    elif query.data == 'change_status':
        await handle_change_status(update, context)

async def handle_add_product(update: Update, context: CallbackContext) -> None:
    """Обробка додавання товару"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    context.user_data['admin_action'] = 'add_product'
    
    await query.edit_message_text("Оберіть категорію для додавання:")
    categories = ["accessories", "iphone", "phones", "smartphones", "watches"]
    keyboard = [
        [InlineKeyboardButton("🎧 Аксесуари", callback_data='category_accessories')],
        [InlineKeyboardButton("🍏 IPhone", callback_data='category_iphone')],
        [InlineKeyboardButton("📞 Телефони", callback_data='category_phones')],
        [InlineKeyboardButton("📱 Смартфони", callback_data='category_smartphones')],
        [InlineKeyboardButton("⌚ Годинники", callback_data='category_watches')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_reply_markup(reply_markup=reply_markup)

async def handle_delete_product(update: Update, context: CallbackContext) -> None:
    """Обробка видалення товару"""
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    context.user_data['admin_action'] = 'delete_product'
    
    await query.edit_message_text("Оберіть категорію для видалення:")
    keyboard = [
        [InlineKeyboardButton("🎧 Аксесуари", callback_data='delete_category_accessories')],
        [InlineKeyboardButton("🍏 IPhone", callback_data='delete_category_iphone')],
        [InlineKeyboardButton("📞 Телефони", callback_data='delete_category_phones')],
        [InlineKeyboardButton("📱 Смартфони", callback_data='delete_category_smartphones')],
        [InlineKeyboardButton("⌚ Годинники", callback_data='delete_category_watches')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_reply_markup(reply_markup=reply_markup)

async def handle_edit_product(update: Update, context: CallbackContext) -> None:
    """Обробка редагування товару"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    context.user_data['admin_action'] = 'edit_product'
    
    await query.edit_message_text("Оберіть категорію для редагування:")
    keyboard = [
        [InlineKeyboardButton("🎧 Аксесуари", callback_data='edit_category_accessories')],
        [InlineKeyboardButton("🍏 IPhone", callback_data='edit_category_iphone')],
        [InlineKeyboardButton("📞 Телефони", callback_data='edit_category_phones')],
        [InlineKeyboardButton("📱 Смартфони", callback_data='edit_category_smartphones')],
        [InlineKeyboardButton("⌚ Годинники", callback_data='edit_category_watches')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_reply_markup(reply_markup=reply_markup)

async def handle_access_change_buttons(update: Update, context: CallbackContext, action: str) -> None:
    query = update.callback_query
    await query.answer()
    
    if action == 'cancel_access_change':
        await query.edit_message_text("❌ Зміну рівня доступу скасовано.")
        return
    
    username = context.user_data.get('username_to_change')
    if not username:
        await query.edit_message_text("🔴 Помилка: користувача не знайдено. Спробуйте ще раз.")
        return
    
    # Визначаємо новий рівень доступу
    new_access = "admin" if action == 'set_access_admin' else "user"
    
    result = db_security.users.update_one(
        {"login": username},
        {"$set": {"access_level": new_access}}
    )
    
    if result.modified_count > 0:
        await query.edit_message_text(
            f"✅ Рівень доступу користувача **{username}** змінено на `{new_access}`!",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"🔴 Помилка: не вдалося оновити запис (або користувач не знайдений).",
            parse_mode="Markdown"
        )
    
    context.user_data.pop('username_to_change', None)
    
async def handle_list_users(update: Update, context: CallbackContext) -> None:
    """Вивід списку користувачів"""
    query = update.callback_query
    user_list = users.find({})
    message = "📋 Список користувачів:\n\n"
    for user in user_list:
        message += f"👤 {user.get('login', 'Невідомо')} - {user.get('email', 'Невідомо')}\n"
        message += f"   Статус: {user.get('status', 'Невідомо')}\n"
        message += f"   Рівень доступу: {user.get('access_level', 'user')}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='admin_back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)

async def handle_change_status(update: Update, context: CallbackContext) -> None:
    """Запит логіну користувача для зміни рівня доступу"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ Введіть логін користувача, якому потрібно змінити рівень доступу:")
    context.user_data['awaiting_username_for_access'] = True

async def handle_block_user(update: Update, context: CallbackContext) -> None:
    """Обробка блокування користувача"""
    query = update.callback_query
    await query.edit_message_text("Введіть логін користувача для блокування:")
    context.user_data['awaiting_user_to_block'] = True

def setup_handlers(application):
    """Налаштування обробників"""
    application.add_handler(MessageHandler(
        filters.TEXT & (
            filters.Regex(r'^📋 Каталог$') |
            filters.Regex(r'^👤 Акаунт$') |
            filters.Regex(r'^🛒 Кошик$') |
            filters.Regex(r'^❓ Допомога$') |
            filters.Regex(r'^🛑 СТОП$') |
            filters.Regex(r'^⚙ Адміністрування$') |
            filters.Regex(r'^📦 Товари$') |
            filters.Regex(r'^👥 Користувачі$') |
            filters.Regex(r'^🆘 Допомога$') |
            filters.Regex(r'^🔙 Назад$')
        ),
        handle_keyboard_buttons
    ))
    
    application.add_handler(CallbackQueryHandler(
        handle_admin_buttons,
        pattern=r'^(add_product|delete_product|edit_product|list_users|change_status|block_user|admin_back)$'
    ))