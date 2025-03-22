import os  # Додано імпорт модуля os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
import admin  # Імпортуємо модуль admin
import account  # Імпортуємо модуль account
import category  # Імпортуємо модуль category
from pymongo import MongoClient
from gridfs import GridFS

# Підключення до MongoDB
client = MongoClient('mongodb://localhost:27017/')
db_security = client['security']  # База даних для користувачів
db_goods = client['goods']  # База даних для товарів
fs = GridFS(db_goods)

# Функція для очищення context.user_data
def clear_user_data(context: CallbackContext):
    context.user_data.clear()

async def start(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    await update.message.reply_text('Привіт, я бот, який допоможе тобі обрати смартфон')
    keyboard = [
        [InlineKeyboardButton("📱 Смартфони", callback_data='smartphones')],
        [InlineKeyboardButton("📞 Телефони", callback_data='phones')],
        [InlineKeyboardButton("🍏 IPhone", callback_data='iphone')],
        [InlineKeyboardButton("⌚ Годинники", callback_data='watches')],
        [InlineKeyboardButton("🎧 Аксесуари", callback_data='accessories')]
    ]
    category_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Обери категорію:', reply_markup=category_markup)

async def help(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    await update.message.reply_text("Привіт, для початку роботи виконай команду /start\n, а якщо потрібно перейти в каталог, то виконай команду /catalog\n")

async def about(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    await update.message.reply_text("Сайт створений для Кваліфікаційної роботи студента групи 42-ІПЗ Павловича Васися\n")

async def catalog(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    categories = ["accessories", "iphone", "phones", "smartphones", "watches"]
    message = "Ось наш каталог:\n\n"

    for category_name in categories:
        products = db_goods[category_name].find()  # Використовуємо базу даних goods
        message += f"<b>{category_name.capitalize()}</b>\n"
        for product in products:
            message += f"- {product['name']}: {product['description']}\n"
        message += "\n"

    await update.message.reply_text(message)

async def stop(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    await update.message.reply_text("Всі поточні дії скасовано. Ви можете почати знову.")

async def status(update: Update, context: CallbackContext) -> None:
    # Використовуємо функцію з модуля admin
    await admin.status(update, context, db_security, db_goods)

# Функція для обробки CallbackQuery (кнопок)
async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    # Перевіряємо, чи це кнопка з модуля account
    if query.data in ['create_account_yes', 'create_account_no', 'login', 'edit_account', 'logout', 'cancel']:
        await account.button_callback(update, context)
    # Перевіряємо, чи це кнопка з модуля category
    elif query.data.startswith(('smartphones', 'phones', 'iphone', 'watches', 'accessories', 'next_', 'detail_')):
        await category.button_callback(update, context, db_goods)  # Передаємо db_goods
    # Перевіряємо, чи це кнопка з модуля admin
    elif query.data.startswith(('add_product', 'delete_product', 'edit_product', 'category_')):
        await admin.button_callback(update, context, db_security, db_goods)

# Функція для обробки повідомлень
async def handle_message(update: Update, context: CallbackContext) -> None:
    # Перевіряємо, чи це повідомлення для модуля account
    if 'awaiting_login' in context.user_data or 'awaiting_password' in context.user_data or 'awaiting_email' in context.user_data or 'awaiting_verification' in context.user_data or 'awaiting_login_for_login' in context.user_data or 'awaiting_verification_for_login' in context.user_data or 'awaiting_password_for_unlock' in context.user_data or 'awaiting_password_for_edit' in context.user_data or 'awaiting_new_login' in context.user_data:
        await account.handle_message(update, context)
    # Інакше передаємо повідомлення до модуля admin
    else:
        await admin.handle_message(update, context, db_security, db_goods)

def main() -> None:
    application = Application.builder().token("7699287813:AAEyWJ7LJ9jn_9wvBxV-fQZ_fy1Y-QjeHUU").build()

    # Додаємо обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("catalog", catalog))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("account", account.account))

    # Додаємо обробник для CallbackQuery (кнопок)
    application.add_handler(CallbackQueryHandler(button_callback))

    # Додаємо обробник для повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))

    application.run_polling()


main()