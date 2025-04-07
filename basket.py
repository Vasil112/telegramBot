from pymongo import MongoClient
from bson import ObjectId
from telegram import Update
from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup 
import services
import bonus

from dotenv import load_dotenv
import os
load_dotenv() 

# Підключення до MongoDB 
client = MongoClient(os.getenv("MONGO_URI"))
db = client['security']  
basket = db['basket'] 
users = db['users']  
db_goods = client['goods']

__all__ = ['basket', 'users', 'db_goods', 'view_basket', 'handle_delete_from_cart', 'handle_add_to_cart', 'handle_place_order', 'handle_order_confirmation', 'services']

async def view_basket(update: Update, context: CallbackContext) -> None:
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        message = update.callback_query.message
    else:
        user_id = update.message.from_user.id
        message = update.message

    basket_items = list(basket.find({"user_id": user_id}))

    if not basket_items:
        await message.reply_text("Ваш кошик порожній.")
        return

    message_text = "Ваш кошик:\n\n"
    total_price = 0
    keyboard = []

    for item in basket_items:
        product_name = item['product_name']
        quantity = item['quantity']
        price = item['price']
        total_price = sum(float(item['price']) * int(item['quantity']) for item in basket_items)
        total_price = bonus.apply_discount(user_id, total_price)
        message_text += f"📦 {product_name}\nКількість: {quantity}\nЦіна: {price} грн\n\n"

        delete_button = InlineKeyboardButton(f"Видалити {product_name}", callback_data=f"delete_item_{item['_id']}")
        keyboard.append([delete_button])

    message_text += f"Загальна сума: {total_price} грн"

    order_button = InlineKeyboardButton("До замовлення", callback_data="place_order")
    keyboard.append([order_button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(message_text, reply_markup=reply_markup)
    
        
async def handle_delete_from_cart(update: Update, context: CallbackContext, item_id: str) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        if item_id.startswith("delete_item_"):
            item_id = item_id.split("_")[-1] 
            
        object_id = ObjectId(item_id)
        
        result = basket.delete_one({"_id": object_id, "user_id": user_id})

        if result.deleted_count > 0:
            await query.message.reply_text("Товар видалено з кошика.")
            user = users.find_one({"user_id": user_id})
            if user:
                users.update_one(
                    {"user_id": user_id},
                    {"$inc": {"basket": -1}} 
                )
        else:
            await query.message.reply_text("Не вдалося видалити товар.")

        await view_basket(update, context)
        
    except Exception as e:
        print(f"Помилка при видаленні товару: {e}")
        await query.message.reply_text("Сталася помилка при видаленні товару. Спробуйте ще раз.")

        
async def handle_add_to_cart(update: Update, context: CallbackContext, product_id: str):
    user_id = update.callback_query.from_user.id
    product = None
    product_category = None

    # Пошук товару в усіх категоріях
    categories = ["accessories", "iphone", "phones", "smartphones", "watches"]
    for category in categories:
        product = db_goods[category].find_one({"_id": ObjectId(product_id)})
        if product:
            product_category = category  
            break

    if not product:
        await update.callback_query.message.reply_text("Товар не знайдено.")
        return

    # Отримуємо дані про товар
    product_name = product.get('name', 'Невідомий товар')
    product_price = product.get('price', '0')
    product_quantity_in_stock = int(product['quantity']) if isinstance(product['quantity'], str) else product['quantity']

    if product_quantity_in_stock <= 0:
        await update.callback_query.message.reply_text("Товар закінчився.")
        return

    existing_item = basket.find_one({"user_id": user_id, "product_id": ObjectId(product_id)})
    if existing_item:
        new_quantity = int(existing_item['quantity']) + 1  
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
            "quantity": int(1), 
            "price": int(product_price),
            "category": product_category 
        })
        await update.callback_query.message.reply_text(f"Товар {product_name} додано до кошика.")

    user = users.find_one({"user_id": user_id})
    if user:
        users.update_one(
            {"user_id": user_id},
            {"$inc": {"basket": 1}}  
        )

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
        await services.offer_full_protection(update, context)
    elif data == "cancel_order":
        await query.message.reply_text("Операцію скасовано. Товари залишаються у вашому кошику.")