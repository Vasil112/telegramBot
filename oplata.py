from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler
from pymongo import MongoClient
from datetime import datetime
import requests
import json
import time
import os
from bson import ObjectId
import spam
import bonus
from bonus import apply_discount
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
users = db['users'] 

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
    
    # Отримуємо дані користувача з context.user_data
    full_name = context.user_data.get('order_full_name', 'Не вказано')
    phone = context.user_data.get('order_phone', 'Не вказано')
    address = context.user_data.get('order_address', 'Не вказано')

    # Розраховуємо загальну суму
    total_price = sum(float(item['price']) * int(item['quantity']) for item in basket_items)
    
    # Застосовуємо знижку на основі статусу користувача
    discounted_price = apply_discount(user_id, total_price)
    user = users.find_one({"user_id": user_id})
    discount_percent = user.get('user_discount', 0) if user else 0
    
    # Зберігаємо оригінальну та знижену ціну
    context.user_data['original_price'] = total_price
    context.user_data['discounted_price'] = discounted_price
    
    amount_kopiyky = int(discounted_price * 100)  # Конвертуємо в копійки
    
    if amount_kopiyky < 100:
        await query.message.reply_text("Мінімальна сума оплати - 1 грн")
        return
    
    # Створюємо замовлення з урахуванням знижки
    order_data = {
        "user_id": user_id,
        "full_name": full_name,
        "phone": phone,
        "address": address,
        "items": basket_items,
        "original_price": total_price,
        "total_price": discounted_price,
        "status": "Очікує оплати",
        "payment_method": "Monobank",
        "created_at": datetime.now()
    }
    order = orders.insert_one(order_data)
    order_id = order.inserted_id
            
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
            "amount": discounted_price,  # Зберігаємо суму зі знижкою
            "original_amount": total_price,  # Зберігаємо оригінальну суму
            "discount_percent": discount_percent,  # Зберігаємо відсоток знижки
            "status": "pending",
            "created_at": datetime.now(),
            "monobank_data": invoice_info,
            "invoice_url": invoice_info['pageUrl'],
            "order_reference": invoice_data['merchantPaymInfo']['reference']
        }
        payments.insert_one(payment_record)

        # Відправляємо повідомлення з реквізитами (додано інформацію про знижку)
        message = f"""
💳 *Оплата через Monobank*

💰 *Початкова сума:* {total_price} грн
💎 *Ваша знижка:* {discount_percent}%
💰 *Сума до оплати зі знижкою:* {discounted_price} грн
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
        await query.message.reply_text("❌ Платіж не знайдено в нашій системі!")
        return
    
    try:
        headers = {
            "X-Token": MONOBANK_MERCHANT_TOKEN,
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{MONOBANK_API_URL}/api/merchant/invoice/status?invoiceId={payment_id}",
            headers=headers
        )
        response.raise_for_status()
        status_info = response.json()
        
        print(f"Статус платежу від Monobank: {status_info}")
        
        if status_info.get('status') == "success":
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
            
            if order and 'items' in order:
                for item in order['items']:
                    try:
                        # Пропускаємо товари з is_protection=True
                        if item.get('is_protection', False):
                            continue
                            
                        # Перевіряємо наявність обов'язкових полів
                        if not all(key in item for key in ['category', 'product_id', 'quantity']):
                            print(f"Попередження: товар має недостатні дані: {item}")
                            continue
                            
                        category_name = item['category']
                        product_id = item['product_id']
                        
                        # Оновлюємо кількість товару
                        db_goods[category_name].update_one(
                            {"_id": ObjectId(product_id)},
                            {"$inc": {"quantity": -int(item['quantity'])}}
                        )
                    except Exception as item_error:
                        print(f"Помилка при оновленні товару {item.get('product_id')}: {item_error}")
                        continue
                    
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
            user = users.find_one({"user_id": query.from_user.id})
            message = f"""
✅ Замовлення оформлено!

📋 Деталі замовлення:
👤 ПІБ: {order.get('full_name', 'Не вказано')}
📞 Телефон: {order.get('phone', 'Не вказано')}
🏠 Адреса: {order.get('address', 'Не вказано')}
💳 Спосіб оплати: {order.get('payment_method', 'Monobank')}
💰 Початкова сума: {order.get('original_price', 0)} грн
💎 Ваша знижка: {user.get('user_discount', 0)}%
💰 Загальна сума зі знижкою: {order.get('total_price', 0)} грн

Дякуємо за замовлення!
"""
            await query.message.reply_text(message)
            await bonus.update_status_after_purchase(query.from_user.id, order.get('total_price', 0), context)
            
            # Отримуємо email користувача з бази даних
            user = users.find_one({"user_id": query.from_user.id})
            if user and user.get('email'):
                try:
                    await spam.send_order_confirmation(update, context, ObjectId(payment['order_id']))
                    await query.message.reply_text(f"📧 Лист з підтвердженням замовлення було надіслано на {user['email']}")
                except Exception as e:
                    print(f"Помилка при відправці листа: {e}")
                    await query.message.reply_text("❌ Не вдалося надіслати лист з підтвердженням. Будь ласка, перевірте ваш email у профілі.")
            else:
                await query.message.reply_text("ℹ️ Email не вказано в профілі. Лист з підтвердженням не було надіслано.")
            
            # Очищаємо контекст
            context.user_data.clear()
        
        elif status_info.get('status') == "processing":
            await query.message.reply_text("🔄 Платіж в обробці. Будь ласка, зачекайте декілька хвилин і спробуйте ще раз.")
        
        elif status_info.get('status') == "failure":
            await query.message.reply_text("❌ Платіж не пройшов. Спробуйте ще раз або оберіть інший спосіб оплати.")
        
        elif status_info.get('status') == "expired":
            await query.message.reply_text("⌛ Час на оплату минув. Будь ласка, створіть нове замовлення.")
        
        else:
            await query.message.reply_text(f"ℹ️ Статус платежу: {status_info.get('status', 'невідомий')}. Якщо ви вже оплатили, будь ласка, зачекайте декілька хвилин.")
    
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP помилка при перевірці платежу: {e.response.status_code}\n"
        if e.response.status_code == 400:
            try:
                error_details = e.response.json()
                error_msg += f"Деталі: {error_details.get('errorDescription', 'Невідома помилка')}"
            except:
                error_msg += f"Текст помилки: {e.response.text}"
        print(error_msg)
        await query.message.reply_text("❌ Помилка при перевірці статусу платежу. Спробуйте пізніше.")
    
    except Exception as e:
        print(f"Неочікувана помилка при перевірці платежу: {str(e)}")
        await query.message.reply_text("❌ Сталася неочікувана помилка при перевірці платежу. Спробуйте ще раз або зверніться до підтримки.")


async def payment_instructions(update: Update, context: CallbackContext) -> None:
    print(">>> Інструкція requested")  # Додаємо логування
    query = update.callback_query
    try:
        await query.answer()
        print(">>> Callback answered")
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="📌 Тестова інструкція - функція працює!",
            parse_mode="HTML"
        )
        print(">>> Повідомлення відправлено")
    except Exception as e:
        print(f">>> Помилка: {str(e)}")

def setup_handlers(application):
    # Реєструємо обробник інструкцій окремо з більш конкретним шаблоном
    application.add_handler(CallbackQueryHandler(
        payment_instructions, 
        pattern=r"^payment_instructions$"
    ))
    
    # Інші обробники
    application.add_handler(CallbackQueryHandler(
        handle_monobank_payment, 
        pattern="^payment_prepay$"
    ))
    application.add_handler(CallbackQueryHandler(
        verify_payment, 
        pattern="^verify_payment_"
    ))