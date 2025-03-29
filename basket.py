from pymongo import MongoClient
from bson import ObjectId
from telegram import Update
from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup 
import services

from dotenv import load_dotenv
import os
load_dotenv()  # Завантажує змінні з .env

# Підключення до MongoDB 
client = MongoClient(os.getenv("MONGO_URI"))
db = client['security']  # Використовуємо базу даних security
basket = db['basket']  # Колекція для кошика
users = db['users']  # Колекція для користувачів
db_goods = client['goods']

__all__ = ['basket', 'users', 'db_goods', 'view_basket', 'handle_delete_from_cart', 'handle_add_to_cart', 'handle_place_order', 'handle_order_confirmation', 'services']

async def view_basket(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    basket_items = list(basket.find({"user_id": user_id}))

    if not basket_items:
        await update.callback_query.message.reply_text("Ваш кошик порожній.")
        return

    message = "Ваш кошик:\n\n"
    total_price = 0
    keyboard = []

    for item in basket_items:
        product_name = item['product_name']
        quantity = item['quantity']
        price = item['price']
        total_price += int(price) * quantity
        message += f"📦 {product_name}\nКількість: {quantity}\nЦіна: {price} грн\n\n"

        # Додаємо кнопку "Видалити" для кожного товару
        delete_button = InlineKeyboardButton(f"Видалити {product_name}", callback_data=f"delete_item_{item['_id']}")
        keyboard.append([delete_button])

    message += f"Загальна сума: {total_price} грн"

    # Додаємо кнопку "До замовлення"
    order_button = InlineKeyboardButton("До замовлення", callback_data="place_order")
    keyboard.append([order_button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(message, reply_markup=reply_markup)
    
async def handle_delete_from_cart(update: Update, context: CallbackContext, item_id: str) -> None:
    user_id = update.callback_query.from_user.id

    # Видаляємо товар з кошика
    result = basket.delete_one({"_id": ObjectId(item_id), "user_id": user_id})

    if result.deleted_count > 0:
        await update.callback_query.message.reply_text("Товар видалено з кошика.")
        # Оновлюємо кількість товарів у кошику користувача
        user = users.find_one({"user_id": user_id})
        if user:
            users.update_one(
                {"user_id": user_id},
                {"$inc": {"basket": -1}}  # Зменшуємо кількість товарів у кошику на 1
            )
    else:
        await update.callback_query.message.reply_text("Не вдалося видалити товар.")

    # Показуємо оновлений кошик
    await view_basket(update, context)

async def handle_add_to_cart(update: Update, context: CallbackContext, product_id: str):
    user_id = update.callback_query.from_user.id
    product = None

    # Пошук товару в усіх категоріях
    categories = ["accessories", "iphone", "phones", "smartphones", "watches"]
    for category in categories:
        product = db_goods[category].find_one({"_id": ObjectId(product_id)})
        if product:
            break

    if not product:
        await update.callback_query.message.reply_text("Товар не знайдено.")
        return

    # Отримуємо дані про товар
    product_name = product.get('name', 'Невідомий товар')
    product_price = product.get('price', '0')
    product_quantity_in_stock = int(product['quantity']) if isinstance(product['quantity'], str) else product['quantity']

    # Перевіряємо, чи є достатня кількість товару в наявності
    if product_quantity_in_stock <= 0:
        await update.callback_query.message.reply_text("Товар закінчився.")
        return

    # Перевіряємо, чи товар вже є в кошику користувача
    existing_item = basket.find_one({"user_id": user_id, "product_id": ObjectId(product_id)})
    if existing_item:
        # Якщо товар вже є в кошику, збільшуємо кількість
        new_quantity = int(existing_item['quantity']) + 1  # Перетворюємо на int
        basket.update_one(
            {"_id": existing_item['_id']},
            {"$set": {"quantity": new_quantity}}
        )
        await update.callback_query.message.reply_text(f"Товар {product_name} вже є у вашому кошику. Кількість збільшено до {new_quantity}.")
    else:
        # Якщо товару немає в кошику, додаємо новий запис
        basket.insert_one({
            "user_id": user_id,
            "product_id": ObjectId(product_id),
            "product_name": product_name,
            "quantity": int(1),  # Переконуємося, що це int
            "price": int(product_price)
        })
        await update.callback_query.message.reply_text(f"Товар {product_name} додано до кошика.")

    # Оновлення кількості товарів у кошику користувача
    user = users.find_one({"user_id": user_id})
    if user:
        users.update_one(
            {"user_id": user_id},
            {"$inc": {"basket": 1}}  # Збільшуємо кількість товарів у кошику на 1
        )

    # Очищення context.user_data після додавання до кошика
    context.user_data.clear()

async def handle_place_order(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    basket_items = list(basket.find({"user_id": user_id}))

    if not basket_items:
        await update.callback_query.message.reply_text("Ваш кошик порожній.")
        return

    # Формуємо список товарів у кошику
    message = "Ваш кошик:\n\n"
    total_price = 0
    for item in basket_items:
        product_name = item['product_name']
        quantity = item['quantity']
        price = item['price']
        total_price += int(price) * quantity
        message += f"📦 {product_name}\nКількість: {quantity}\nЦіна: {price} грн\n\n"

    message += f"Загальна сума: {total_price} грн\n\nБажаєте продовжити?"

    # Кнопки "Так" і "Ні"
    keyboard = [
        [InlineKeyboardButton("Так", callback_data="confirm_order")],
        [InlineKeyboardButton("Ні", callback_data="cancel_order")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(message, reply_markup=reply_markup)

async def handle_place_order(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    basket_items = list(basket.find({"user_id": user_id}))

    if not basket_items:
        await update.callback_query.message.reply_text("Ваш кошик порожній.")
        return

    # Формуємо список товарів у кошику
    message = "Ваш кошик:\n\n"
    total_price = 0
    for item in basket_items:
        product_name = item['product_name']
        quantity = item['quantity']
        price = item['price']
        total_price += int(price) * quantity
        message += f"📦 {product_name}\nКількість: {quantity}\nЦіна: {price} грн\n\n"

    message += f"Загальна сума: {total_price} грн\n\nБажаєте продовжити?"

    # Кнопки "Так" і "Ні"
    keyboard = [
        [InlineKeyboardButton("Так", callback_data="confirm_order")],
        [InlineKeyboardButton("Ні", callback_data="cancel_order")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(message, reply_markup=reply_markup)

async def handle_order_confirmation(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "confirm_order":
        # Пропонуємо сервіс "Full Protection"
        await services.offer_full_protection(update, context)
    elif data == "cancel_order":
        await query.message.reply_text("Операцію скасовано. Товари залишаються у вашому кошику.")