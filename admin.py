import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from pymongo.database import Database
import io
from bson import ObjectId
from gridfs import GridFS

from dotenv import load_dotenv
import os
load_dotenv()  # Завантажує змінні з .env

# Списки характеристик для різних категорій
SMARTPHONES_CHARACTERISTICS = [
    "Кількість sim-карт", "Стандарти зв'язку", "Діагональ екрану", "Роздільна здатність дисплея",
    "Частота оновлення екрану", "Тип екрану", "Процесор", "Кількість ядер", "Частота процесора",
    "Внутрішня пам'ять", "Оперативна пам'ять", "Камера", "Запис відео", "Фронтальна камера",
    "Операційна система", "Bluetooth", "NFC", "Безпровідна зарядка", "Інтерфейси і підключення",
    "Матеріал корпуса", "Технології", "Ємність акумулятора", "Швидка зарядка", "Комплектація", "Гарантійний термін"
]

PHONES_CHARACTERISTICS = [
    "Кількість sim-карт", "Стандарти зв'язку", "Діагональ екрану", "Роздільна здатність дисплея",
    "Тип екрану", "Процесор", "Камера", "Операційна система", "Wi-fi", "Bluetooth", "NFC",
    "Інтерфейси і підключення", "Матеріал корпуса", "Додатково", "Ємність акумулятора",
    "Швидка зарядка", "Комплектація", "Гарантійний термін"
]

IPHONE_CHARACTERISTICS = [
    "Кількість sim-карт", "Стандарти зв'язку", "Діагональ екрану", "Роздільна здатність дисплея",
    "Частота оновлення екрану", "Тип екрану", "Процесор", "Внутрішня пам'ять", "Камера", "Запис відео",
    "Фронтальна камера", "Операційна система", "Bluetooth", "NFC", "Безпровідна зарядка", "Інтерфейси і підключення",
    "Матеріал корпуса", "Технології", "Ємність акумулятора", "Швидка зарядка", "Комплектація", "Гарантійний термін"
]

WATCHES_CHARACTERISTICS = [
    "Тип матриці", "Розмір дисплея", "Роздільна здатність дисплея", "Сенсорний екран", "Процесор",
    "Флеш пам'ять", "Оперативна пам'ять", "Сумісність", "Операційна система", "Бездротові технології та роз'єми",
    "Wi-Fi", "Bluetooth", "NFC", "Наявність камери", "Наявність SIM-карти", "Дзвінки та оповіщення", "Датчики",
    "Функції", "Спосіб зарядки", "Ємність акумулятора", "Форма", "Матеріал корпуса", "Комплектація", "Гарантійний термін"
]

# Функція для обробки команди /status для адміністратора
async def status(update: Update, context: CallbackContext, db_security: Database, db_goods: Database) -> None:
    # Отримуємо user_id з update.message або update.callback_query
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        await update.message.reply_text("Неможливо отримати інформацію про користувача.")
        return

    user = db_security.users.find_one({"user_id": user_id})  # Використовуємо базу даних security для користувачів

    # Перевіряємо, чи користувач вийшов з акаунту
    if context.user_data.get('logged_out', False):
        await update.message.reply_text("У вас немає доступу до цієї команди. Будь ласка, увійдіть у свій акаунт.")
        return

    # Перевіряємо статус користувача
    if user and user.get('status') == 'active' and user.get('access_level') == 'admin':
        keyboard = [
            [InlineKeyboardButton("Додати товар", callback_data='add_product')],
            [InlineKeyboardButton("Видалити товар", callback_data='delete_product')],
            [InlineKeyboardButton("Редагувати товар", callback_data='edit_product')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Оберіть дію:", reply_markup=reply_markup)
    elif user and user.get('status') == 'passive':
        await update.message.reply_text("Будь ласка, увійдіть до свого облікового запису.")
    else:
        await update.message.reply_text("У вас немає доступу до цієї команди.")

# Функція для обробки натискання кнопок у /status
async def handle_admin_callback(update: Update, context: CallbackContext, db_security: Database, db_goods: Database) -> None:
    query = update.callback_query
    await query.answer()
    
    print(f"\n--- BUTTON PRESSED ---")
    print(f"Button data: {query.data}")
    print(f"Current user_data BEFORE: {context.user_data}")
    
    if query.data == 'add_product':
        context.user_data.clear()
        context.user_data['admin_action'] = 'add_product'
        print(f"user_data AFTER add_product: {context.user_data}")
        
        await query.edit_message_text(text="Оберіть категорію для нового товару:")
        categories_keyboard = [
            [InlineKeyboardButton("🎧 Аксесуари", callback_data='category_accessories')],
            [InlineKeyboardButton("🍏 IPhone", callback_data='category_iphone')],
            [InlineKeyboardButton("📞 Телефони", callback_data='category_phones')],
            [InlineKeyboardButton("📱 Смартфони", callback_data='category_smartphones')],
            [InlineKeyboardButton("⌚ Годинники", callback_data='category_watches')]
        ]
        reply_markup = InlineKeyboardMarkup(categories_keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    
    elif query.data == 'edit_product':
        # Не очищаємо context.user_data повністю, лише встановлюємо admin_action
        context.user_data['admin_action'] = 'edit_product'
        print(f"user_data AFTER edit_product: {context.user_data}")
        
        await start_edit_product(update, context)
    
    elif query.data.startswith('category_'):
        if 'admin_action' not in context.user_data:
            await query.edit_message_text("Помилка: не почато процес додавання/редагування товару")
            return
            
        category = query.data.split('_')[1]
        context.user_data.update({
            'category': category,
            'awaiting_product_name': True if context.user_data['admin_action'] == 'add_product' else False,
            'awaiting_product_name_for_edit': True if context.user_data['admin_action'] == 'edit_product' else False,
            'current_step': 'name'
        })
        print(f"user_data AFTER category select: {context.user_data}")
        
        if context.user_data['admin_action'] == 'add_product':
            await query.edit_message_text(text=f"✅ Ви обрали категорію: {category}\nВведіть назву товару:")
        else:
            await query.edit_message_text(text=f"✅ Ви обрали категорію: {category}\nВведіть назву товару, який потрібно редагувати:")
    
    print(f"user_data FINAL: {context.user_data}")


async def start_edit_product(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()  # Підтверджуємо отримання callback

    keyboard = [
        [InlineKeyboardButton("🎧 Аксесуари", callback_data='edit_category_accessories')],
        [InlineKeyboardButton("🍏 iPhone", callback_data='edit_category_iphone')],
        [InlineKeyboardButton("📞 Телефони", callback_data='edit_category_phones')],
        [InlineKeyboardButton("📱 Смартфони", callback_data='edit_category_smartphones')],
        [InlineKeyboardButton("⌚ Годинники", callback_data='edit_category_watches')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Використовуємо query.edit_message_text для редагування повідомлення
    await query.edit_message_text("📌 Оберіть категорію товару:", reply_markup=reply_markup)

async def handle_category_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    category_map = {
        "edit_category_accessories": "accessories",
        "edit_category_iphone": "iphone",
        "edit_category_phones": "phones",
        "edit_category_smartphones": "smartphones",
        "edit_category_watches": "watches"
    }

    selected_category = category_map.get(query.data)
    if selected_category:
        context.user_data['category'] = selected_category
        await query.edit_message_text(f"✅ Ви обрали категорію: {selected_category}\nВведіть назву товару, який потрібно редагувати:")
        context.user_data['awaiting_product_name_for_edit'] = True


# Функція для обробки повідомлень
async def handle_message(update: Update, context: CallbackContext, db_security: Database, db_goods: Database) -> None:
    
    fs = GridFS(db_goods)  # Ініціалізуємо GridFS для збереження фото


    # Отримання назви товару
    if context.user_data.get('admin_action') == 'add_product' and context.user_data.get('awaiting_product_name'):
        product_name = update.message.text
        if not product_name.strip():
            await update.message.reply_text("Назва товару не може бути порожньою. Спробуйте ще раз:")
            return
        
        context.user_data.update({
            'product_name': product_name,
            'awaiting_product_name': False,
            'awaiting_product_description': True,
            'current_step': 'description'
        })
        await update.message.reply_text("Введіть опис товару:")
        return  # Важливо: завершуємо обробку поточного повідомлення
    
    # Отримання опису товару
    elif 'awaiting_product_description' in context.user_data:
        product_description = update.message.text
        if product_description == ".":
            # Якщо користувач ввів крапку, залишаємо попередній опис
            context.user_data['product_description'] = context.user_data.get('original_product_description', '')
        else:
            context.user_data['product_description'] = product_description
        await update.message.reply_text("Введіть ціну товару:")
        context.user_data['awaiting_product_price'] = True
        del context.user_data['awaiting_product_description']
    
    # Отримання ціни товару
    elif 'awaiting_product_price' in context.user_data:
        product_price = update.message.text
        try:
            if product_price == ".":
                # Якщо користувач ввів крапку, залишаємо попередню ціну
                context.user_data['product_price'] = int(context.user_data.get('original_product_price', 0))
            else:
                # Конвертуємо введене значення в ціле число
                context.user_data['product_price'] = int(product_price)
        except ValueError:
            await update.message.reply_text("Будь ласка, введіть коректну ціну (ціле число):")
            return
            
        await update.message.reply_text("Введіть кількість товару:")
        context.user_data['awaiting_product_quantity'] = True
        del context.user_data['awaiting_product_price']
        
    # Отримання кількості товару
    elif 'awaiting_product_quantity' in context.user_data:
        product_quantity = update.message.text
        if product_quantity == ".":
            # Якщо користувач ввів крапку, залишаємо попередню кількість
            context.user_data['product_quantity'] = context.user_data.get('original_product_quantity', 0)
        else:
            context.user_data['product_quantity'] = int(product_quantity) if product_quantity.isdigit() else 0

        # Якщо категорія - аксесуари, пропускаємо характеристики
        if context.user_data['category'] == 'accessories':
            await update.message.reply_text("Тепер надішліть фото товару:")
            context.user_data['awaiting_product_photo'] = True
        else:
            context.user_data['product_specs'] = {}  # Створюємо словник характеристик
            context.user_data['current_spec_index'] = 0  # Починаємо з першої характеристики

            # Визначаємо, який список характеристик використовувати
            category = context.user_data['category']
            if category == "smartphones":
                characteristics_list = SMARTPHONES_CHARACTERISTICS
            elif category == "phones":
                characteristics_list = PHONES_CHARACTERISTICS
            elif category == "iphone":
                characteristics_list = IPHONE_CHARACTERISTICS
            elif category == "watches":
                characteristics_list = WATCHES_CHARACTERISTICS
            else:
                characteristics_list = []  # Для інших категорій характеристики не потрібні

            if characteristics_list:
                await update.message.reply_text(f"Введіть значення для характеристики: {characteristics_list[0]}")
                context.user_data['awaiting_product_specs'] = True
            else:
                await update.message.reply_text("Тепер надішліть фото товару:")
                context.user_data['awaiting_product_photo'] = True
        del context.user_data['awaiting_product_quantity']
    
    # Отримання характеристик товару по черзі
    elif 'awaiting_product_specs' in context.user_data:
        index = context.user_data['current_spec_index']
        category = context.user_data['category']
        
        # Визначаємо, який список характеристик використовувати
        if category == "smartphones":
            characteristics_list = SMARTPHONES_CHARACTERISTICS
        elif category == "phones":
            characteristics_list = PHONES_CHARACTERISTICS
        elif category == "iphone":
            characteristics_list = IPHONE_CHARACTERISTICS
        elif category == "watches":
            characteristics_list = WATCHES_CHARACTERISTICS
        else:
            characteristics_list = []

        spec_value = update.message.text.strip()
        if spec_value == ".":
            # Якщо користувач ввів крапку, залишаємо попереднє значення характеристики
            spec_value = context.user_data['product_specs'].get(characteristics_list[index], '')
        
        context.user_data['product_specs'][characteristics_list[index]] = spec_value

        # Перевіряємо, чи ще є характеристики для заповнення
        if index + 1 < len(characteristics_list):
            context.user_data['current_spec_index'] += 1
            next_spec = characteristics_list[context.user_data['current_spec_index']]
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
            "price": context.user_data['product_price'],
            "quantity": context.user_data['product_quantity'],  # Додаємо кількість товару
            "specs": context.user_data.get('product_specs', {}),  # Характеристики (якщо є)
            "photo_id": photo_id  # Зберігаємо ObjectId фото
        }
        category = context.user_data['category']
        db_goods[category].insert_one(product)

        await update.message.reply_text(f"✅ Товар успішно додано до категорії {category}!\n📸 Фото збережено в базі.")
        context.user_data.clear()

    # Обробка видалення товару за назвою
    elif 'awaiting_product_name_for_delete' in context.user_data:
        product_name = update.message.text
        category = context.user_data.get('category')

        if category:
            result = db_goods[category].delete_one({"name": product_name})
            if result.deleted_count > 0:
                await update.message.reply_text(f"Товар з назвою '{product_name}' успішно видалено з категорії {category}.")
            else:
                await update.message.reply_text(f"Товар з назвою '{product_name}' не знайдено в категорії {category}.")
        else:
            await update.message.reply_text("Категорія не вказана. Спробуйте ще раз.")

        del context.user_data['awaiting_product_name_for_delete']

    elif 'awaiting_product_name_for_edit' in context.user_data:
        if 'category' not in context.user_data:
            await update.message.reply_text("⚠ Категорія товару не обрана. Будь ласка, спочатку вкажіть категорію.")
            return
        
        product_name = update.message.text
        context.user_data['product_name_for_edit'] = product_name
        await update.message.reply_text("Введіть нову назву товару (або введіть '.', щоб залишити попередню назву):")
        context.user_data['awaiting_new_product_name'] = True
        del context.user_data['awaiting_product_name_for_edit']

    # Обробка редагування товару за назвою
    elif 'awaiting_product_name_for_edit' in context.user_data:
        product_name = update.message.text
        category = context.user_data['category']
        product = db_goods[category].find_one({"name": product_name})
        
        if product:
            # Зберігаємо всі оригінальні значення
            context.user_data.update({
                'original_product_name': product['name'],
                'original_product_description': product['description'],
                'original_product_price': product['price'],
                'original_product_quantity': product['quantity'],
                'original_product_specs': product.get('specs', {}),
                'product_name_for_edit': product_name  # Зберігаємо оригінальну назву для пошуку
            })
            
            print(f"\n--- DEBUG: ORIGINAL PRODUCT DATA SAVED ---")
            print(f"Original name: {context.user_data['original_product_name']}")
            print(f"Original description: {context.user_data['original_product_description']}")
            
            await update.message.reply_text("Введіть нову назву товару (або введіть '.', щоб залишити попередню назву):")
            context.user_data['awaiting_new_product_name'] = True
        else:
            await update.message.reply_text("Товар не знайдено.")
        
        del context.user_data['awaiting_product_name_for_edit']
        
    # У функції handle_message, де обробляється 'awaiting_new_product_name':
    elif 'awaiting_new_product_name' in context.user_data:
        new_product_name = update.message.text
        if new_product_name == ".":
            # Використовуємо оригінальну назву, переконуючись, що вона є
            if 'original_product_name' not in context.user_data:
                await update.message.reply_text("Помилка: оригінальна назва не знайдена. Будь ласка, введіть нову назву:")
                return
            context.user_data['new_product_name'] = context.user_data['original_product_name']
        else:
            context.user_data['new_product_name'] = new_product_name
        
        print(f"\n--- DEBUG: NEW PRODUCT NAME SET ---")
        print(f"Original name: {context.user_data.get('original_product_name')}")
        print(f"New name: {context.user_data.get('new_product_name')}")
        
        await update.message.reply_text("Введіть новий опис товару (або введіть '.', щоб залишити попередній опис):")
        context.user_data['awaiting_new_product_description'] = True
        del context.user_data['awaiting_new_product_name']
            
    # Отримання нового опису товару для редагування
    elif 'awaiting_new_product_description' in context.user_data:
        new_product_description = update.message.text
        if new_product_description == ".":
            # Використовуємо оригінальний опис
            context.user_data['new_product_description'] = context.user_data.get('original_product_description', '')
        else:
            context.user_data['new_product_description'] = new_product_description
        await update.message.reply_text("Введіть нову ціну товару (або введіть '.', щоб залишити попередню ціну):")
        context.user_data['awaiting_new_product_price'] = True
        del context.user_data['awaiting_new_product_description']

    # Отримання нової ціни товару для редагування
    elif 'awaiting_new_product_price' in context.user_data:
        new_product_price = update.message.text
        try:
            if new_product_price == ".":
                # Використовуємо оригінальну ціну
                context.user_data['new_product_price'] = int(context.user_data.get('original_product_price', 0))
            else:
                # Конвертуємо введене значення в ціле число
                context.user_data['new_product_price'] = int(new_product_price)
        except ValueError:
            await update.message.reply_text("Будь ласка, введіть коректну ціну (ціле число):")
            return
            
        await update.message.reply_text("Введіть нову кількість товару (або введіть '.', щоб залишити попередню кількість):")
        context.user_data['awaiting_new_product_quantity'] = True
        del context.user_data['awaiting_new_product_price']
            
    # Отримання нової кількості товару для редагування
    elif 'awaiting_new_product_quantity' in context.user_data:
        new_product_quantity = update.message.text
        if new_product_quantity == ".":
            # Використовуємо оригінальну кількість
            context.user_data['new_product_quantity'] = context.user_data.get('original_product_quantity', 0)
        else:
            context.user_data['new_product_quantity'] = int(new_product_quantity) if new_product_quantity.isdigit() else 0

        # Оновлюємо товар у базі даних
        category = context.user_data.get('category')
        product_name = context.user_data.get('product_name_for_edit')

        # Переконуємося, що є категорія і назва товару
        if not category or not product_name:
            await update.message.reply_text("❌ Категорія або назва товару не вказані. Будь ласка, спробуйте ще раз.")
            return

        # Перевіряємо, чи товар існує в базі
        existing_product = db_goods[category].find_one({"name": product_name})
        if not existing_product:
            await update.message.reply_text(f"❌ Помилка: товар '{product_name}' не знайдено в категорії {category}.")
            return

        if category and product_name:
            result = db_goods[category].update_one(
                {"name": product_name},
                {"$set": {
                    "name": context.user_data['new_product_name'],
                    "description": context.user_data['new_product_description'],
                    "price": context.user_data['new_product_price'],
                    "quantity": context.user_data['new_product_quantity'],
                    "specs": context.user_data.get('original_product_specs', {})  # Зберігаємо оригінальні характеристики
                }}
            )

            if result.matched_count > 0:
                await update.message.reply_text(f"✅ Товар '{product_name}' успішно оновлено в категорії {category}.")
            else:
                await update.message.reply_text(f"❌ Помилка: товар '{product_name}' не знайдено в категорії {category}.")
        else:
            await update.message.reply_text("❌ Категорія або назва товару не вказані. Спробуйте ще раз.")

        # Очищаємо context.user_data
        keys_to_delete = [
            'awaiting_new_product_quantity',
            'product_name_for_edit',
            'original_product_name',
            'original_product_description',
            'original_product_price',
            'original_product_quantity',
            'original_product_specs'
        ]

        # Перевіряємо, чи змінна keys_to_delete ініціалізована
        if 'keys_to_delete' in locals():
            for key in keys_to_delete:
                if key in context.user_data:
                    del context.user_data[key]
        else:
            # Якщо keys_to_delete не ініціалізована, просто очищаємо context.user_data
            context.user_data.clear()