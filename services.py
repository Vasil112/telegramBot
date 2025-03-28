from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from pymongo import MongoClient
from bson import ObjectId

from dotenv import load_dotenv
import os
load_dotenv()  # Завантажує змінні з .env

client = MongoClient(os.getenv("MONGO_URI"))
db_security = client['security']
db_goods = client['goods']
basket = db_security['basket']

async def offer_full_protection(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    basket_items = list(basket.find({"user_id": user_id}))

    # Перевіряємо, чи вже є Full Protection у кошику
    if any(item.get('is_protection') for item in basket_items):
        await continue_order(update, context)
        return

    # Знаходимо всі телефони у кошику
    phone_items = []
    total_phone_price = 0
    
    for item in basket_items:
        product_id = item.get('product_id')
        if not product_id:
            continue
            
        for category in ['smartphones', 'phones', 'iphone']:
            if db_goods[category].find_one({"_id": ObjectId(product_id)}):
                phone_items.append(item)
                total_phone_price += int(item['price']) * item['quantity']
                break

    if not phone_items:
        await continue_order(update, context)
        return

    # Розраховуємо ціни для різних термінів
    price_24 = int(total_phone_price * 0.4)
    price_12 = int(total_phone_price * 0.3)
    price_6 = int(total_phone_price * 0.25)

    message = (
        "Хочемо запропонувати вам сервіс Full Protection, який повністю захистить ваш пристрій.\n"
        f"Вартість послуги розрахована на основі вартості ваших телефонів ({total_phone_price} грн).\n\n"
        "Оберіть термін дії послуги:"
    )

    keyboard = [
        [InlineKeyboardButton(f"24 місяці ({price_24} грн)", callback_data=f"full_protection_24_{price_24}")],
        [InlineKeyboardButton(f"12 місяців ({price_12} грн)", callback_data=f"full_protection_12_{price_12}")],
        [InlineKeyboardButton(f"6 місяців ({price_6} грн)", callback_data=f"full_protection_6_{price_6}")],
        [InlineKeyboardButton("Не цікавить", callback_data="no_protection")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        reply_markup=reply_markup
    )

async def handle_protection_choice(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "no_protection":
        await query.message.reply_text("Дякуємо за ваше рішення.")
    else:
        parts = data.split('_')
        duration = parts[2]
        price = int(parts[3])
        
        # Додаємо послугу до кошика
        user_id = query.from_user.id
        basket.insert_one({
            "user_id": user_id,
            "product_name": f"Full Protection ({duration} місяців)",
            "price": price,
            "quantity": int(1),
            "is_protection": True
        })
        
        await query.message.reply_text(
            f"Додано Full Protection на {duration} місяців за {price} грн до вашого замовлення."
        )

    # Показуємо оновлений кошик
    await continue_order(update, context)

async def continue_order(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    basket_items = list(basket.find({"user_id": user_id}))

    if not basket_items:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Ваш кошик порожній."
        )
        return

    message = "Ваше замовлення:\n\n"
    total_price = 0

    for item in basket_items:
        product_name = item['product_name']
        quantity = item['quantity']
        price = int(item['price'])
        item_total = price * quantity
        total_price += item_total
        message += f"📦 {product_name}\nКількість: {quantity}\nЦіна: {price} грн\nСума: {item_total} грн\n\n"

    message += f"Загальна сума: {total_price} грн\n\nОформляємо замовлення?"

    keyboard = [
        [InlineKeyboardButton("Підтвердити замовлення", callback_data="confirm_final_order")],
        [InlineKeyboardButton("Скасувати", callback_data="cancel_order")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        reply_markup=reply_markup
    )