from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from pymongo import MongoClient
import random
import string

# Підключення до MongoDB
client = MongoClient('mongodb://mongo:YdCyhskWWhVayCaoAkBApdPEbozlaXwE@hopper.proxy.rlwy.net:17259')
db = client['security']
users_collection = db['users']

# Функція для генерації випадкового коду
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

async def account(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = users_collection.find_one({"user_id": user_id})

    if user:
        await update.message.reply_text(f"Інформація про ваш акаунт:\nЛогін: {user['login']}\nПароль: {user['password']}")
    else:
        # Створення кнопок "Так" і "Ні"
        keyboard = [
            [InlineKeyboardButton("Так", callback_data='create_account_yes')],
            [InlineKeyboardButton("Ні", callback_data='create_account_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Акаунт не знайдено. Бажаєте створити новий акаунт?", reply_markup=reply_markup)

async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'create_account_yes':
        await query.edit_message_text(text="Введіть логін:")
        context.user_data['awaiting_login'] = True  # Позначаємо, що очікуємо логін
    elif query.data == 'create_account_no':
        await query.edit_message_text(text="Створення акаунту скасовано.")

async def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    if 'awaiting_login' in context.user_data:
        # Користувач ввів логін
        login = update.message.text
        context.user_data['login'] = login
        context.user_data['awaiting_password'] = True  # Позначаємо, що очікуємо пароль
        del context.user_data['awaiting_login']  # Видаляємо прапор очікування логіну
        await update.message.reply_text("Введіть пароль:")
    elif 'awaiting_password' in context.user_data:
        # Користувач ввів пароль
        password = update.message.text
        context.user_data['password'] = password
        context.user_data['awaiting_phone'] = True  # Позначаємо, що очікуємо номер телефону
        del context.user_data['awaiting_password']  # Видаляємо прапор очікування паролю
        await update.message.reply_text("Введіть ваш номер телефону:")
    elif 'awaiting_phone' in context.user_data:
        # Користувач ввів номер телефону
        phone = update.message.text
        context.user_data['phone'] = phone

        # Генеруємо код підтвердження
        verification_code = generate_verification_code()
        context.user_data['verification_code'] = verification_code

        # Надсилаємо код користувачу
        await update.message.reply_text(f"Код підтвердження: {verification_code}\nВведіть цей код для завершення реєстрації.")
        context.user_data['awaiting_verification'] = True  # Позначаємо, що очікуємо код підтвердження
        del context.user_data['awaiting_phone']  # Видаляємо прапор очікування номера телефону
    elif 'awaiting_verification' in context.user_data:
        # Користувач ввів код підтвердження
        user_code = update.message.text
        if user_code == context.user_data['verification_code']:
            # Код вірний, зберігаємо акаунт у MongoDB
            users_collection.insert_one({
                "user_id": user_id,
                "login": context.user_data['login'],
                "password": context.user_data['password'],
                "phone": context.user_data['phone'],
                "status": "user"
            })

            await update.message.reply_text("Акаунт успішно створено!")
            # Очищаємо дані
            del context.user_data['awaiting_verification']
            del context.user_data['verification_code']
            del context.user_data['login']
            del context.user_data['password']
            del context.user_data['phone']
        else:
            await update.message.reply_text("Невірний код підтвердження. Спробуйте ще раз.")