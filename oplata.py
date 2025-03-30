from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler
from pymongo import MongoClient
from datetime import datetime
import requests
import json
import time
import os
from bson import ObjectId

from dotenv import load_dotenv
import os
load_dotenv()  # Завантажує змінні з .env

to_date = int(time.time())  # Поточний час
from_date = to_date - 86400  # Мінус 24 години

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db = client['security']
orders = db['orders']
payments = db['payments']
basket_collection = db['basket']  # Перейменуємо, щоб уникнути конфлікту з імпортом модуля

# Налаштування Monobank API
MONOBANK_API_URL = "https://api.monobank.ua"
MONOBANK_MERCHANT_TOKEN = os.getenv("MONOBANK_MERCHANT_TOKEN")  #! Виправлено - використовуємо змінну оточення
MONOBANK_CARD = os.getenv("MONOBANK_CARD")  # Ваш номер картки Monobank

async def handle_monobank_payment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    basket_items = list(basket_collection.find({"user_id": user_id}))
    
    if not basket_items:
        await query.message.reply_text("Ваш кошик порожній!")
        return
    
    # Отримуємо дані користувача (якщо вони є в user_data)
    full_name = context.user_data.get('full_name', 'Не вказано')
    phone = context.user_data.get('phone', 'Не вказано')
    address = context.user_data.get('address', 'Не вказано')

    # Розраховуємо загальну суму
    total_price = sum(float(item['price']) * int(item['quantity']) for item in basket_items)
    amount_kopiyky = int(total_price * 100)  # Конвертуємо в копійки
    
    if amount_kopiyky < 100:
        await query.message.reply_text("Мінімальна сума оплати - 1 грн")
        return
    
    # 1️⃣ Спочатку створюємо замовлення
    order_data = {
        "user_id": user_id,
        "full_name": full_name,
        "phone": phone,
        "address": address,
        "items": basket_items,
        "total_price": total_price,
        "status": "Очікує оплати",
        "payment_method": "Monobank",
        "created_at": datetime.now()
    }
    order = orders.insert_one(order_data)
    order_id = order.inserted_id  # Отримуємо ID нового замовлення
        
    # Створюємо інвойс в Monobank
    invoice_data = {
        "amount": amount_kopiyky,
        "ccy": 980,  # UAH
        "merchantPaymInfo": {
            "reference": f"order_{user_id}_{int(time.time())}",
            "destination": "Оплата товарів",
            "comment": "Оплата замовлення"
        },
        "redirectUrl": "https://t.me/storeManager_112Bot",  # URL для перенаправлення після оплати
        "webHookUrl": "https://your-webhook-url.com/monobank",  # URL для отримання статусу
        "validity": 3600,  # 1 година
        "paymentType": "debit"
    }
    
    try:
        response = requests.post(
            f"{MONOBANK_API_URL}/api/merchant/invoice/create",
            json=invoice_data,
            headers={"X-Token": MONOBANK_MERCHANT_TOKEN}
        )
        response.raise_for_status()
        invoice_info = response.json()
        
        payment_record = {
            "user_id": user_id,
            "payment_id": invoice_info['invoiceId'],
            "order_id": order_id,  # Додаємо ID замовлення
            "amount": total_price,
            "status": "pending",
            "created_at": datetime.now(),
            "monobank_data": invoice_info,
            "invoice_url": invoice_info['pageUrl'],
            "order_reference": invoice_data['merchantPaymInfo']['reference']
        }
        payments.insert_one(payment_record)

        # Відправляємо повідомлення з реквізитами
        message = f"""
💳 *Оплата через Monobank*

💰 *Сума до оплати:* {total_price} грн
📋 *Призначення платежу:* {payment_record['order_reference']}

Для оплати перейдіть за посиланням:
{invoice_info['pageUrl']}

*Після оплати натисніть кнопку "Підтвердити оплату".*
"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 Підтвердити оплату", callback_data=f"verify_payment_{invoice_info['invoiceId']}")],
            [InlineKeyboardButton("ℹ️ Інструкція", callback_data="payment_instructions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"Помилка HTTP при створенні інвойсу: {e.response.status_code}\n"
        if e.response.status_code == 400:
            try:
                error_details = e.response.json()
                error_msg += f"Деталі: {error_details.get('errorDescription', 'Невідома помилка')}"
            except:
                error_msg += f"Текст помилки: {e.response.text}"
        print(error_msg)
        await query.message.reply_text("❌ Помилка при створенні рахунку. Спробуйте пізніше або оберіть інший спосіб оплати.")
    
    except Exception as e:
        print(f"Неочікувана помилка: {str(e)}")
        await query.message.reply_text("❌ Сталася неочікувана помилка. Спробуйте ще раз або зверніться до підтримки.")

async def verify_payment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    payment_id = query.data.split("_")[-1]
    payment = payments.find_one({"payment_id": payment_id})
    
    if not payment:
        await query.message.reply_text("Платіж не знайдено!")
        return
    
    try:
        headers = {
            "X-Token": MONOBANK_MERCHANT_TOKEN
        }
        
        response = requests.get(
            f"https://api.monobank.ua/api/merchant/invoice/status?invoiceId={payment_id}",
            headers={
                "X-Token": "MONOBANK_MERCHANT_TOKEN",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        status_info = response.json()
        
        if status_info['status'] == "success":
            # Оновлюємо статус платежу
            payments.update_one(
                {"payment_id": payment_id},
                {"$set": {
                    "status": "paid",
                    "paid_at": datetime.now(),
                    "monobank_status": status_info
                }}
            )
            
            # Оновлюємо кількість товарів у базі даних
            client = MongoClient(os.getenv("MONGO_URI"))
            db_goods = client['goods']
            order = orders.find_one({"_id": ObjectId(payment['order_id'])})
            
            for item in order['items']:
                category_name = item['category']
                product_id = item['product_id']
                
                # Оновлюємо кількість товару
                db_goods[category_name].update_one(
                    {"_id": ObjectId(product_id)},
                    {"$inc": {"quantity": -int(item['quantity'])}}
                )
            
            # Оновлюємо статус замовлення
            orders.update_one(
                {"_id": ObjectId(payment['order_id'])},
                {"$set": {
                    "status": "Оплачено",
                    "payment_status": "paid",
                    "payment_details": status_info
                }}
            )
            
            # Видаляємо кошик
            basket_collection.delete_many({"user_id": query.from_user.id})
            
            # Відправляємо підтвердження
            order = orders.find_one({"_id": ObjectId(payment['order_id'])})
            message = f"""
✅ Замовлення оформлено!

📋 Деталі замовлення:
👤 ПІБ: {order['full_name']}
📞 Телефон: {order['phone']}
🏠 Адреса: {order['address']}
💳 Спосіб оплати: {order['payment_method']}
💰 Загальна сума: {order['total_price']} грн

Дякуємо за замовлення!
"""
            await query.message.reply_text(message)
            
            # Очищаємо контекст
            context.user_data.clear()
        else:
            await query.message.reply_text(f"❌ Статус платежу: {status_info['status']}. Будь ласка, спробуйте ще раз або зверніться до підтримки.")
    
    except Exception as e:
        print(f"Помилка при перевірці статусу платежу: {e}")
        await query.message.reply_text("❌ Сталася помилка при перевірці статусу платежу. Спробуйте ще раз.")


async def payment_instructions(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📌 Інструкція з оплати:\n\n"
        "1. Перейдіть за посиланням для оплати\n"
        "2. Увійдіть у свій Monobank або виберіть інший спосіб оплати\n"
        "3. Підтвердіть платіж\n"
        "4. Поверніться до чату та натисніть 'Підтвердити оплату'\n\n"
        "Якщо виникли проблеми, зверніться до підтримки."
    )

def setup_handlers(application):
    application.add_handler(CallbackQueryHandler(handle_monobank_payment, pattern="^payment_prepay$"))
    application.add_handler(CallbackQueryHandler(verify_payment, pattern="^verify_payment_"))
    application.add_handler(CallbackQueryHandler(payment_instructions, pattern="^payment_instructions$"))