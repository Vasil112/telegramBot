from pymongo import MongoClient
from bson import ObjectId
from telegram import Update
from telegram.ext import CallbackContext

# Підключення до MongoDB 
client = MongoClient('mongodb://localhost:27017/')
db_goods = client['goods']
db_security = client['security']
basket_collection = db_security['basket']

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
    existing_item = basket_collection.find_one({"user_id": user_id, "product_id": ObjectId(product_id)})
    if existing_item:
        # Якщо товар вже є в кошику, збільшуємо кількість
        new_quantity = int(existing_item['quantity']) + 1  # Перетворюємо на int
        basket_collection.update_one(
            {"_id": existing_item['_id']},
            {"$set": {"quantity": new_quantity}}
        )
        await update.callback_query.message.reply_text(f"Товар {product_name} вже є у вашому кошику. Кількість збільшено до {new_quantity}.")
    else:
        # Якщо товару немає в кошику, додаємо новий запис
        basket_collection.insert_one({
            "user_id": user_id,
            "product_id": ObjectId(product_id),
            "product_name": product_name,
            "quantity": int(1),  # Переконуємося, що це int
            "price": product_price
        })
        await update.callback_query.message.reply_text(f"Товар {product_name} додано до кошика.")

    # Очищення context.user_data після додавання до кошика
    context.user_data.clear()