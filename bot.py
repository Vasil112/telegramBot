import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
import admin  # Імпортуємо модуль admin
import account  # Імпортуємо модуль account
import category  # Імпортуємо модуль category
import basket  # Імпортуємо модуль basket
import services  # Імпортуємо модуль services
import history  # Імпортуємо модуль history
from pymongo import MongoClient
from gridfs import GridFS

# Підключення до MongoDB
client = MongoClient('mongodb://localhost:27017/')
db_security = client['security']  # База даних для користувачів
db_goods = client['goods']  # База даних для товарів
fs = GridFS(db_goods)
user_addresses = db_security['user_addresses']  # Колекція для адрес користувачів

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

    data = query.data

    # Обробка кнопок для модуля account
    if data in ['create_account_yes', 'create_account_no', 'login', 'edit_account', 'logout', 'cancel']:
        await account.handle_account_callback(update, context)
    
    # Обробка кнопок для модуля category
    elif data.startswith(('smartphones', 'phones', 'iphone', 'watches', 'accessories', 'next_', 'prev_', 'detail_', 'cart_', 'buy_')):
        await category.handle_category_callback(update, context, db_goods)
    
    # Обробка кнопок для вибору категорії при редагуванні
    elif data.startswith("edit_category_"):
        await admin.handle_category_selection(update, context)

    # Обробка кнопок для модуля admin
    elif data.startswith(('add_product', 'delete_product', 'edit_product', 'category_')):
        await admin.handle_admin_callback(update, context, db_security, db_goods)
    
    # Обробка кнопки "Кошик"
    elif data == 'view_basket':
        await basket.view_basket(update, context)
    
    # Обробка кнопки "Видалити" з кошика
    elif data.startswith("delete_"):
        item_id = data.split("_")[1]
        await basket.handle_delete_from_cart(update, context, item_id)
    
    # Обробка кнопки "До замовлення"
    elif data == "place_order":
        await basket.handle_place_order(update, context)
    
    # Обробка підтвердження замовлення
    elif data in ["confirm_order", "cancel_order"]:
        await basket.handle_order_confirmation(update, context)
    
    # Обробка вибору сервісу "Full Protection"
    elif data.startswith("full_protection_") or data == "no_protection":
        await services.handle_protection_choice(update, context)
    
    elif data == 'manage_address':
        await handle_manage_address(update, context)

    elif data == "confirm_final_order":
        await history.confirm_final_order(update, context)
    elif data == "add_new_address":
        await history.handle_address_selection(update, context)
    elif data.startswith("select_address_"):
        await history.handle_address_selection(update, context)
    elif data.startswith("save_address_"):
        await history.handle_address_save_decision(update, context)
    elif data.startswith("payment_"):
        await history.handle_payment(update, context)


async def handle_manage_address(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    addresses = list(user_addresses.find({"user_id": user_id}))
    
    if addresses:
        message = "Ваші збережені адреси:\n\n" + "\n".join([f"📍 {addr['address']}" for addr in addresses])
        keyboard = [
            [InlineKeyboardButton("Додати нову адресу", callback_data="add_new_address")],
            [InlineKeyboardButton("Видалити адресу", callback_data="delete_address")]
        ]
    else:
        message = "У вас немає збережених адрес."
        keyboard = [[InlineKeyboardButton("Додати адресу", callback_data="add_new_address")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(message, reply_markup=reply_markup)

# Функція для обробки повідомлень
async def handle_message(update: Update, context: CallbackContext) -> None:
    # Спочатку перевіряємо, чи очікується адреса
    if context.user_data.get('awaiting_address'):
        await history.handle_address(update, context)
        return
    
    # Потім інші перевірки для account
    elif ('awaiting_login' in context.user_data or ...):
        await account.handle_message(update, context)
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


    history.setup_handlers(application)
    application.run_polling()

main()  