import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler, PicklePersistence
import admin 
import account 
import category  
import basket  
import services  
import history  
import oplata 
import address  
import keyboard_buttons 
import history_basket
import search
from history_basket import setup_handlers as setup_history_handlers
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
import bonus
from dotenv import load_dotenv
 
load_dotenv() 
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Підключення до MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db_security = client['security']  
db_goods = client['goods'] 
fs = GridFS(db_goods)
user_addresses = db_security['user_addresses'] 

def clear_user_data(context: CallbackContext):
    context.user_data.clear()

async def start(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    await update.message.reply_text('Привіт, я бот, який допоможе тобі обрати смартфон')
    await keyboard_buttons.show_main_keyboard(update, context)  


async def help(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    await update.message.reply_text("Привіт, для початку роботи виконай команду /start\n, а якщо потрібно перейти в каталог, то виконай команду /catalog\n")

async def about(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    await update.message.reply_text("Бот створений для Кваліфікаційної роботи студента групи 42-ІПЗ Павловича Василя\n")

async def catalog(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    categories = ["accessories", "iphone", "phones", "smartphones", "watches"]
    message = "Ось наш каталог:\n\n"

    for category_name in categories:
        products = db_goods[category_name].find() 
        message += f"<b>{category_name.capitalize()}</b>\n"
        for product in products:
            message += f"- {product['name']}: {product['description']}\n"
        message += "\n"

    await update.message.reply_text(message)

async def stop(update: Update, context: CallbackContext) -> None:
    clear_user_data(context)
    await update.message.reply_text("Всі поточні дії скасовано. Ви можете почати знову.")
    await keyboard_buttons.show_main_keyboard(update, context)  

async def status(update: Update, context: CallbackContext) -> None:
    await admin.status(update, context, db_security, db_goods)

async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data

    if data in ['create_account_yes', 'create_account_no', 'login', 'edit_account', 'logout', 'cancel']:
        await account.handle_account_callback(update, context)
    
    elif data in ['set_access_admin', 'set_access_user', 'cancel_access_change']:
        await keyboard_buttons.handle_access_change_buttons(update, context, data)
    
    elif data.startswith(('smartphones', 'phones', 'iphone', 'watches', 'accessories', 'next_', 'prev_', 'detail_', 'cart_', 'buy_')):
        await category.handle_category_callback(update, context, db_goods)
    
    elif data.startswith("edit_category_"):
        await admin.handle_category_selection(update, context)

    elif data.startswith(('add_product', 'delete_product', 'edit_product', 'category_', 'delete_category_', 'edit_category_')):
        await admin.handle_admin_callback(update, context, db_security, db_goods)
    
    elif data == 'view_basket':
        await basket.view_basket(update, context)
    
    elif data.startswith("delete_item_"):
        item_id = data
        await basket.handle_delete_from_cart(update, context, item_id)

    elif data == "place_order":
        await basket.handle_place_order(update, context)
    
    elif data in ["confirm_order", "cancel_order"]:
        await basket.handle_order_confirmation(update, context)
    
    elif data.startswith("full_protection_") or data == "no_protection":
        await services.handle_protection_choice(update, context)
    
    elif data == 'manage_address':
        await address.handle_manage_address(update, context)
    
    elif data == "delete_address":
        await address.handle_delete_address(update, context)
    
    elif data.startswith("delete_address_"):
        address_id = data.split("_")[-1]
        await address.confirm_delete_address(update, context, address_id)
    
    elif data.startswith("confirm_delete_addr_"):
        address_id = data.split("_")[-1]
        await address.delete_address(update, context, address_id)

    elif data == "confirm_final_order":
        await history.confirm_final_order(update, context)
    elif data == "add_new_address":
        await history.handle_address_selection(update, context)
    elif data.startswith("select_address_"):
        await history.handle_address_selection(update, context)
    elif data.startswith("save_address_"):
        await address.handle_address_save_decision(update, context)
    elif data.startswith("payment_"):
        await history.handle_payment(update, context)
    elif data.startswith("use_saved_data_"):
        await history.handle_use_saved_data_decision(update, context)

    elif data.startswith("verify_payment_"):
        await oplata.verify_payment(update, context)
    elif data == "payment_instructions":
        await oplata.payment_instructions(update, context)
    elif data == "payment_prepay":
        await oplata.handle_monobank_payment(update, context)

    elif data.startswith(('add_product', 'delete_product', 'edit_product', 
                    'category_', 'delete_category_', 'edit_category_',
                    'admin_back')):
        await admin.handle_admin_callback(update, context, db_security, db_goods)




# Функція для обробки повідомлень
async def handle_message(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('awaiting_search_query'):
        await search.search_product(update, context)
        return
    
    if context.user_data.get('awaiting_address'):
        await address.handle_address(update, context)
        return
    elif context.user_data.get('awaiting_username_for_access'):
        username = update.message.text
        context.user_data['username_to_change'] = username
        context.user_data.pop('awaiting_username_for_access', None)
        
        keyboard = [
            [InlineKeyboardButton("Зробити Адміністратором (admin)", callback_data='set_access_admin')],
            [InlineKeyboardButton("Зробити Користувачем (user)", callback_data='set_access_user')],
            [InlineKeyboardButton("Скасувати", callback_data='cancel_access_change')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Оберіть новий рівень доступу для користувача **{username}**:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return 
    
    elif context.user_data.get('awaiting_full_name_for_save'):
        await address.handle_full_name_for_save(update, context)
        return
    
    elif context.user_data.get('awaiting_full_name'):
        await history.handle_full_name(update, context)
        return
    
    elif context.user_data.get('awaiting_phone_for_save'):
        await address.handle_phone_for_save(update, context)
        return
    
    elif context.user_data.get('awaiting_phone'):
        await history.handle_phone_number(update, context)
        return
    
    # Перевіряємо, чи очікується логін або пароль для редагування акаунту
    elif any(key in context.user_data for key in ['awaiting_login', 'awaiting_password', 'awaiting_email', 
                                               'awaiting_verification', 'awaiting_login_for_login',
                                               'awaiting_verification_for_login', 'awaiting_password_for_unlock',
                                               'awaiting_password_for_edit', 'awaiting_new_login']):
        await account.handle_message(update, context)
        return
    
    elif context.user_data.get('admin_action'):
        await admin.handle_message(update, context, db_security, db_goods)
        return
    

def main() -> None:
    persistence = PicklePersistence(filepath='bot_data')
    application = Application.builder() \
        .token(os.getenv("BOT_TOKEN")) \
        .persistence(persistence) \
        .build()
    
    setup_history_handlers(application)
    keyboard_buttons.setup_handlers(application)
    # Додаємо обробники пошуку
    application.add_handler(CallbackQueryHandler(search.handle_search_callback, pattern='^search_product$')) #! потрібно перейменувати бо через цю фігню не працюють 

    # Додаємо обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("catalog", catalog))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("account", account.account))
    application.add_handler(CommandHandler("statuss", bonus.show_status_info))

    application.add_handler(CallbackQueryHandler(button_callback))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    
    
    history_basket.setup_handlers(application)
    oplata.setup_handlers(application)
    history.setup_handlers(application)
    address.setup_handlers(application)
    application.run_polling()

main()  