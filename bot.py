from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
import admin  # Імпортуємо модуль admin
import account  # Імпортуємо модуль account
import category # Імпортуємо модуль category
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
    category = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Обери категорію:', reply_markup=category)

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

    for category in categories:
        products = db_goods[category].find()  # Використовуємо базу даних goods
        message += f"**{category.capitalize()}**\n"
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

    # Передаємо об'єкти баз даних (db_security та db_goods) до функції button_callback у модулі admin
    await admin.button_callback(update, context, db_security, db_goods)

# Функція для обробки повідомлень
async def handle_message(update: Update, context: CallbackContext) -> None:
    # Передаємо об'єкти баз даних (db_security та db_goods) до функції handle_message у модулі admin
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

    # Додаємо обробники з модуля category ПОТІМ
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^(add_product|delete_product|edit_product|category_.*)$"))

    # Додаємо обробники з модуля admin ПЕРШИМИ
    application.add_handler(CallbackQueryHandler(category.button_callback, pattern="^(smartphones|phones|iphone|watches|accessories|next_.*|detail_.*)$"))  # Використовуємо локальну функцію button_callback
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # Використовуємо локальну функцію handle_message
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))  # Використовуємо локальну функцію handle_message



    # Додаємо обробники з модуля account
    application.add_handler(CallbackQueryHandler(account.button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, account.handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()