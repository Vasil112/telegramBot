from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import CallbackContext
from pymongo import MongoClient
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Підключення до MongoDB
client = MongoClient('mongodb://mongo:YdCyhskWWhVayCaoAkBApdPEbozlaXwE@hopper.proxy.rlwy.net:17259')
db = client['security']
users_collection = db['users']

# Токен вашого бота
BOT_TOKEN = "7699287813:AAEyWJ7LJ9jn_9wvBxV-fQZ_fy1Y-QjeHUU"

# Налаштування для надсилання електронної пошти
SMTP_SERVER = "smtp.gmail.com"  # Наприклад, для Gmail
SMTP_PORT = 587
EMAIL_ADDRESS = "oschadbanknotoriginal@gmail.com"  # Ваша електронна пошта
EMAIL_PASSWORD = "qclg exwl lcju wslu"  # Пароль від вашої електронної пошти

# Функція для генерації випадкового коду
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

# Функція для надсилання електронного листа з кодом підтвердження
def send_verification_email(email: str, code: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = "Код підтвердження для реєстрації"

        body = f"Ваш код підтвердження: {code}"
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Помилка при надсиланні електронного листа: {e}")
        return False

async def account(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = users_collection.find_one({"user_id": user_id})

    if user:
        await update.message.reply_text(f"Інформація про ваш акаунт:\nЛогін: {user['login']}\nЕлектронна пошта: {user['email']}\nКількість товарів у кошику: {user['basket']}\nЗагальна кількість замовлень: {user['all_orders']}")
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
    chat_id = update.message.chat_id  # Отримуємо chat_id користувача

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
        context.user_data['awaiting_email'] = True  # Позначаємо, що очікуємо електронну пошту
        del context.user_data['awaiting_password']  # Видаляємо прапор очікування паролю
        await update.message.reply_text("Введіть вашу електронну пошту:")
    elif 'awaiting_email' in context.user_data:
        # Користувач ввів електронну пошту
        email = update.message.text
        context.user_data['email'] = email

        # Генеруємо код підтвердження
        verification_code = generate_verification_code()
        context.user_data['verification_code'] = verification_code

        # Надсилаємо код на електронну пошту
        if send_verification_email(email, verification_code):
            await update.message.reply_text("Код підтвердження надіслано на вашу електронну пошту. Введіть його для завершення реєстрації.")
            context.user_data['awaiting_verification'] = True  # Позначаємо, що очікуємо код підтвердження
            del context.user_data['awaiting_email']  # Видаляємо прапор очікування електронної пошти
        else:
            await update.message.reply_text("Помилка при надсиланні коду підтвердження. Спробуйте ще раз.")
    elif 'awaiting_verification' in context.user_data:
        # Користувач ввів код підтвердження
        user_code = update.message.text
        if user_code == context.user_data['verification_code']:
            # Код вірний, зберігаємо акаунт у MongoDB
            users_collection.insert_one({
                "user_id": user_id,
                "chat_id": chat_id,  # Зберігаємо chat_id
                "login": context.user_data['login'],
                "password": context.user_data['password'],
                "email": context.user_data['email'],  # Зберігаємо електронну пошту
                "status": "user",
                "basket": 0,
                "all_orders": 0
            })

            await update.message.reply_text("Акаунт успішно створено!")
            # Очищаємо дані
            del context.user_data['awaiting_verification']
            del context.user_data['verification_code']
            del context.user_data['login']
            del context.user_data['password']
            del context.user_data['email']
        else:
            await update.message.reply_text("Невірний код підтвердження. Спробуйте ще раз.")

# Функція для надсилання паролю на вказану електронну пошту
async def send_password_to_user(email: str):
    # Знаходимо користувача в базі даних за електронною поштою
    user = users_collection.find_one({"email": email})
    if user:
        chat_id = user['chat_id']
        password = user['password']
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text=f"Ваш пароль: {password}")
    else:
        print("Користувача з такою електронною поштою не знайдено.")