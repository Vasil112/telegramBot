from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from pymongo.database import Database
import io
from bson import ObjectId
from gridfs import GridFS

# Функція для обробки команди /status для адміністратора
async def status(update: Update, context: CallbackContext, db_security: Database, db_goods: Database) -> None:
    user_id = update.message.from_user.id
    user = db_security.users.find_one({"user_id": user_id})  # Використовуємо базу даних security для користувачів

    if user and user.get('access_level') == 'admin':
        keyboard = [
            [InlineKeyboardButton("Додати товар", callback_data='add_product')],
            [InlineKeyboardButton("Видалити товар", callback_data='delete_product')],
            [InlineKeyboardButton("Редагувати товар", callback_data='edit_product')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Оберіть дію:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("У вас немає доступу до цієї команди.")

# Функція для обробки натискання кнопок у /status
async def button_callback(update: Update, context: CallbackContext, db_security: Database, db_goods: Database) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'add_product':
        await query.edit_message_text(text="Оберіть категорію для нового товару:")
        categories_keyboard = [
            [InlineKeyboardButton("Аксесуари", callback_data='category_accessories')],
            [InlineKeyboardButton("IPhone", callback_data='category_iphone')],
            [InlineKeyboardButton("Телефони", callback_data='category_phones')],
            [InlineKeyboardButton("Смартфони", callback_data='category_smartphones')],
            [InlineKeyboardButton("Годинники", callback_data='category_watches')]
        ]
        reply_markup = InlineKeyboardMarkup(categories_keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    elif query.data.startswith('category_'):
        context.user_data['category'] = query.data.split('_')[1]
        await query.edit_message_text(text="Введіть назву товару:")
        context.user_data['awaiting_product_name'] = True
    elif query.data == 'delete_product':
        await query.edit_message_text(text="Функція видалення товару ще в розробці.")
    elif query.data == 'edit_product':
        await query.edit_message_text(text="Функція редагування товару ще в розробці.")

# Функція для обробки повідомлень після вибору категорії
import io
from bson import ObjectId
from gridfs import GridFS

# Список характеристик, які треба заповнити
CHARACTERISTICS_LIST = [
    "Кількість sim-карт", "Стандарти зв'язку", "Діагональ екрану", "Роздільна здатність дисплея",
    "Частота оновлення екрану", "Тип екрану", "Процесор", "Кількість ядер", "Частота процесора",
    "Внутрішня пам'ять", "Оперативна пам'ять", "Камера", "Запис відео", "Фронтальна камера",
    "Операційна система", "Bluetooth", "NFC", "Безпровідна зарядка", "Інтерфейси і підключення",
    "Матеріал корпуса", "Технології", "Ємність акумулятора", "Швидка зарядка", "Комплектація", "Гарантійний термін"
]

async def handle_message(update: Update, context: CallbackContext, db_security: Database, db_goods: Database) -> None:
    fs = GridFS(db_goods)  # Ініціалізуємо GridFS для збереження фото

    # Отримання назви товару
    if 'awaiting_product_name' in context.user_data:
        context.user_data['product_name'] = update.message.text
        await update.message.reply_text("Введіть опис товару:")
        context.user_data['awaiting_product_description'] = True
        del context.user_data['awaiting_product_name']
    
    # Отримання опису товару
    elif 'awaiting_product_description' in context.user_data:
        context.user_data['product_description'] = update.message.text
        await update.message.reply_text("Введіть ціну товару:")
        context.user_data['awaiting_product_price'] = True
        del context.user_data['awaiting_product_description']
    
    # Отримання ціни товару
    elif 'awaiting_product_price' in context.user_data:
        context.user_data['product_price'] = update.message.text
        context.user_data['product_specs'] = {}  # Створюємо словник характеристик
        context.user_data['current_spec_index'] = 0  # Починаємо з першої характеристики

        await update.message.reply_text(f"Введіть значення для характеристики: {CHARACTERISTICS_LIST[0]}")
        context.user_data['awaiting_product_specs'] = True
        del context.user_data['awaiting_product_price']
    
    # Отримання характеристик товару по черзі
    elif 'awaiting_product_specs' in context.user_data:
        index = context.user_data['current_spec_index']
        context.user_data['product_specs'][CHARACTERISTICS_LIST[index]] = update.message.text.strip()

        # Перевіряємо, чи ще є характеристики для заповнення
        if index + 1 < len(CHARACTERISTICS_LIST):
            context.user_data['current_spec_index'] += 1
            next_spec = CHARACTERISTICS_LIST[context.user_data['current_spec_index']]
            await update.message.reply_text(f"Введіть значення для характеристики: {next_spec}")
        else:
            await update.message.reply_text("Усі характеристики введено! Тепер надішліть фото товару:")
            context.user_data['awaiting_product_photo'] = True
            del context.user_data['awaiting_product_specs']
    
    # Завантаження фото товару в MongoDB (GridFS)
    elif 'awaiting_product_photo' in context.user_data:
        if not update.message.photo:
            await update.message.reply_text("Будь ласка, надішліть фото, а не документ.")
            return

        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        # Зберігаємо фото в GridFS
        photo_id = fs.put(io.BytesIO(photo_bytes), filename=f"{context.user_data['product_name']}.jpg")

        # Додаємо товар у базу даних
        product = {
            "name": context.user_data['product_name'],
            "description": context.user_data['product_description'],
            "price": context.user_data['product_price'],  # Додаємо поле price
            "specs": context.user_data['product_specs'],
            "photo_id": photo_id  # Зберігаємо ObjectId фото
        }
        category = context.user_data['category']
        db_goods[category].insert_one(product)

        await update.message.reply_text(f"✅ Товар успішно додано до категорії {category}!\n📸 Фото збережено в базі.")
        context.user_data.clear()