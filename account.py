import os  # Додано імпорт модуля os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import CallbackContext
from pymongo import MongoClient
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from basket import basket

# Підключення до MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['security']
users = db['users']
basket_collection = client['basket']

BOT_TOKEN = "7699287813:AAEyWJ7LJ9jn_9wvBxV-fQZ_fy1Y-QjeHUU"

SMTP_SERVER = "smtp.gmail.com" 
SMTP_PORT = 587
EMAIL_ADDRESS = "oschadbanknotoriginal@gmail.com" 
EMAIL_PASSWORD = "qclg exwl lcju wslu"  

# Функція для генерації випадкового коду
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

# Функція для надсилання електронного листа з кодом підтвердження
def send_verification_email(email: str, code: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = "Код підтвердження для входу"

        body = f"Ваш код підтвердження для входу: {code}"
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
    user = users.find_one({"user_id": user_id})

    # Оновлюємо кількість товарів у кошику перед виведенням інформації
    if user:
        basket_count = basket.count_documents({"user_id": user_id})
        users.update_one({"user_id": user_id}, {"$set": {"basket": basket_count}})

    if user and user.get('status') == 'active' and not context.user_data.get('logged_out', False):
        keyboard = [
            [InlineKeyboardButton("Редагувати", callback_data='edit_account')],
            [InlineKeyboardButton("Кошик", callback_data='view_basket')],  # Додано кнопку "Кошик"
            [InlineKeyboardButton("Вихід", callback_data='logout')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Інформація про ваш акаунт:\nЛогін: {user['login']}\nЕлектронна пошта: {user['email']}\nКількість товарів у кошику: {user['basket']}\nЗагальна кількість замовлень: {user['all_orders']}",
            reply_markup=reply_markup
        )
    else:
        keyboard = [
            [InlineKeyboardButton("Створити новий акаунт", callback_data='create_account_yes')],
            [InlineKeyboardButton("Вхід", callback_data='login')],
            [InlineKeyboardButton("Відмінити", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Що бажаєте зробити?", reply_markup=reply_markup)
        

async def handle_account_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    try:
        if query.data == 'create_account_yes':
            await query.edit_message_text(text="Введіть логін:")
            context.user_data['awaiting_login'] = True  
        elif query.data == 'create_account_no':
            await query.edit_message_text(text="Створення акаунту скасовано.")
        elif query.data == 'login':
            await query.edit_message_text(text="Введіть ваш логін:")
            context.user_data['awaiting_login_for_login'] = True  
        elif query.data == 'edit_account':
            await query.edit_message_text(text="Введіть ваш пароль для підтвердження:")
            context.user_data['awaiting_password_for_edit'] = True  
        elif query.data == 'logout':
            context.user_data['logged_out'] = True  # Встановлюємо прапорець logged_out
            users.update_one({"user_id": query.from_user.id}, {"$set": {"status": "pasive"}})
            context.user_data.clear()  # Очищаємо context.user_data
            keyboard = [
                [InlineKeyboardButton("Створити новий акаунт", callback_data='create_account_yes')],
                [InlineKeyboardButton("Вхід", callback_data='login')],
                [InlineKeyboardButton("Відмінити", callback_data='cancel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text="Ви успішно вийшли з акаунту. Що бажаєте зробити?", reply_markup=reply_markup)
        elif query.data == 'cancel':
            await query.edit_message_text(text="Дію скасовано.")
        elif query.data == 'view_basket':  # Обробка кнопки "Кошик"
            await view_basket(update, context)
    except Exception as e:
        print(f"Помилка при редагуванні повідомлення: {e}")

async def view_basket(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    basket_items = basket_collection.find({"user_id": user_id})

    if basket_items.count() == 0:
        await update.callback_query.message.reply_text("Ваш кошик порожній.")
        return

    message = "Ваш кошик:\n\n"
    total_price = 0

    for item in basket_items:
        product_name = item['product_name']
        quantity = item['quantity']
        price = item['price']
        total_price += int(price) * quantity
        message += f"📦 {product_name}\nКількість: {quantity}\nЦіна: {price} грн\n\n"

    message += f"Загальна сума: {total_price} грн"

    await update.callback_query.message.reply_text(message)


async def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id  # Отримуємо chat_id користувача

    if 'awaiting_login' in context.user_data:
        # Користувач ввів логін
        login = update.message.text
        context.user_data['login'] = login
        context.user_data['awaiting_password'] = True  
        del context.user_data['awaiting_login']  
        await update.message.reply_text("Введіть пароль:")
    elif 'awaiting_password' in context.user_data:
        # Користувач ввів пароль
        password = update.message.text
        context.user_data['password'] = password
        context.user_data['awaiting_email'] = True  
        del context.user_data['awaiting_password'] 
        await update.message.reply_text("Введіть вашу електронну пошту:")
    elif 'awaiting_email' in context.user_data:
        email = update.message.text
        context.user_data['email'] = email

        # Генеруємо код підтвердження
        verification_code = generate_verification_code()
        context.user_data['verification_code'] = verification_code

        # Надсилаємо код на електронну пошту
        if send_verification_email(email, verification_code):
            await update.message.reply_text("Код підтвердження надіслано на вашу електронну пошту. Введіть його для завершення реєстрації.")
            context.user_data['awaiting_verification'] = True  
            del context.user_data['awaiting_email']  
        else:
            await update.message.reply_text("Помилка при надсиланні коду підтвердження. Спробуйте ще раз.")
    elif 'awaiting_verification' in context.user_data:
        user_code = update.message.text
        if user_code == context.user_data['verification_code']:
            # Код вірний, зберігаємо акаунт у MongoDB
            users.insert_one({
                "user_id": user_id,
                "chat_id": chat_id,  
                "login": context.user_data['login'],
                "password": context.user_data['password'],
                "email": context.user_data['email'],  
                "status": "active",  
                "basket": 0,
                "all_orders": 0,
                "access_level": "user"
            })

            await update.message.reply_text("Акаунт успішно створено!")
            del context.user_data['awaiting_verification']
            del context.user_data['verification_code']
            del context.user_data['login']
            del context.user_data['password']
            del context.user_data['email']
        else:
            await update.message.reply_text("Невірний код підтвердження. Спробуйте ще раз.")
    elif 'awaiting_login_for_login' in context.user_data:
        login = update.message.text
        user = users.find_one({"login": login})
        if user:
            if user.get('status') == 'pasive':
                await update.message.reply_text("Цей акаунт вимкнено. Введіть пароль для розблокування:")
                context.user_data['awaiting_password_for_unlock'] = True  
                context.user_data['login_for_unlock'] = login  
                del context.user_data['awaiting_login_for_login'] 
                return
            context.user_data['login'] = login
            verification_code = generate_verification_code()
            context.user_data['verification_code'] = verification_code

            if send_verification_email(user['email'], verification_code):
                await update.message.reply_text("Код підтвердження надіслано на вашу електронну пошту. Введіть його для входу.")
                context.user_data['awaiting_verification_for_login'] = True 
                del context.user_data['awaiting_login_for_login']  
            else:
                await update.message.reply_text("Помилка при надсиланні коду підтвердження. Спробуйте ще раз.")
        else:
            await update.message.reply_text("Користувача з таким логіном не знайдено.")
    elif 'awaiting_verification_for_login' in context.user_data:
        user_code = update.message.text
        if user_code == context.user_data['verification_code']:
            await update.message.reply_text("Ви успішно увійшли в акаунт!")
            context.user_data['logged_out'] = False
            context.user_data['device_verified'] = True  
            del context.user_data['awaiting_verification_for_login']
            del context.user_data['verification_code']
        else:
            await update.message.reply_text("Невірний код підтвердження. Спробуйте ще раз.")
    elif 'awaiting_password_for_unlock' in context.user_data:
        password = update.message.text
        login = context.user_data['login_for_unlock']
        user = users.find_one({"login": login, "password": password})
        if user:
            users.update_one({"login": login}, {"$set": {"status": "active"}})
            await update.message.reply_text("Акаунт успішно розблоковано! Ви можете увійти.")
            del context.user_data['awaiting_password_for_unlock']
            del context.user_data['login_for_unlock']
        else:
            await update.message.reply_text("Невірний пароль. Спробуйте ще раз.")
    elif 'awaiting_password_for_edit' in context.user_data:
        password = update.message.text
        user = users.find_one({"user_id": user_id, "password": password})
        if user:
            await update.message.reply_text("Введіть новий логін:")
            context.user_data['awaiting_new_login'] = True  
            del context.user_data['awaiting_password_for_edit']  
        else:
            await update.message.reply_text("Невірний пароль. Спробуйте ще раз.")
    elif 'awaiting_new_login' in context.user_data:
        new_login = update.message.text
        users.update_one({"user_id": user_id}, {"$set": {"login": new_login}})
        await update.message.reply_text("Логін успішно змінено!")
        del context.user_data['awaiting_new_login']  

# Функція для надсилання паролю на вказану електронну пошту
async def send_password_to_user(email: str):
    user = users.find_one({"email": email})
    if user:
        chat_id = user['chat_id']
        password = user['password']
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text=f"Ваш пароль: {password}")
    else:
        print("Користувача з такою електронною поштою не знайдено.")