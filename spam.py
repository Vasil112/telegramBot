from telegram import Update
from telegram.ext import CallbackContext
from pymongo import MongoClient
from bson import ObjectId
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client['security']
orders = db['orders']
users = db['users']

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("EMAIL_ADDRESS")
SMTP_PASSWORD = os.getenv("EMAIL_PASSWORD")  

async def send_order_confirmation(update: Update, context: CallbackContext, order_id: ObjectId) -> None:
    try:
        logger.info(f"Початок обробки замовлення {order_id}")
        
        order = orders.find_one({"_id": order_id})
        if not order:
            error_msg = "❌ Помилка: замовлення не знайдено."
            logger.error(error_msg)
            await update.effective_message.reply_text(error_msg)
            return

        user = users.find_one({"user_id": order["user_id"]})
        if not user:
            error_msg = "❌ Помилка: користувач не знайдений."
            logger.error(error_msg)
            await update.effective_message.reply_text(error_msg)
            return

        user_email = user.get("email")
        if not user_email:
            msg = "✅ Замовлення оформлено! (Але email не вказано в профілі)"
            logger.info(msg)
            await update.effective_message.reply_text(msg)
            return

        logger.info(f"Готуємо лист для {user_email}")

        items_text = "\n".join(
            f"- {item.get('product_name', item.get('name', 'Товар без назви'))} ({item.get('quantity', 1)} шт.) - {float(item.get('price', 0)) * int(item.get('quantity', 1))} грн"
            for item in order["items"]
        )

        if not order.get("items"):
            error_msg = "❌ Помилка: у замовленні відсутні товари."
            logger.error(error_msg)
            await update.effective_message.reply_text(error_msg)
            return

        email_body = f"""
        <html>
        <body>
            <h2>Ваше замовлення #{order_id}</h2>
            <p>Дякуємо за покупку!</p>
            <h3>Деталі:</h3>
            <ul>
                <li>ПІБ: {order.get('full_name', 'Не вказано')}</li>
                <li>Телефон: {order.get('phone', 'Не вказано')}</li>
                <li>Спосіб оплати: {order.get('payment_method', 'Не вказано')}</li>
            </ul>
            <h3>Товари:</h3>
            {items_text}
            <h3>Загальна сума: {order.get('total_price', 0)} грн</h3>
            <p>Якщо у вас виникли питання, зв'яжіться з нами.</p>
        </body>
        </html>
        """

        # Налаштування листа
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = user_email
        msg["Subject"] = f"Підтвердження замовлення #{order_id}"
        msg.attach(MIMEText(email_body, "html"))

        logger.info("Намагаємося підключитися до SMTP сервера")
        
        # Відправляємо листа
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            logger.info(f"Намагаємося увійти з {SMTP_USERNAME}")
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            logger.info("Успішно автентифіковано, відправляємо листа")
            server.send_message(msg)
            logger.info("Лист успішно відправлено")

        # Повідомляємо про успішну відправку
        success_msg = f"✅ Лист з підтвердженням замовлення надіслано на {user_email}"
        logger.info(success_msg)
        await update.effective_message.reply_text(success_msg)

    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"❌ Помилка автентифікації SMTP: {str(e)}"
        logger.error(error_msg)
        await update.effective_message.reply_text(error_msg)
    except smtplib.SMTPException as e:
        error_msg = f"❌ Помилка SMTP: {str(e)}"
        logger.error(error_msg)
        await update.effective_message.reply_text(error_msg)
    except Exception as e:
        error_msg = f"❌ Неочікувана помилка: {str(e)}"
        logger.error(error_msg)
        await update.effective_message.reply_text(error_msg)