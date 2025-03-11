from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
import account

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Привіт, я бот, який допоможе тобі обрати смартфон, вибирай категорію і поїхали')

async def help(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Привіт, для початку роботи виконай команду /start\n, а якщо потрібно перейти в каталог, то виконай команду /catalog\n")

async def about(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Сайт створений для Кваліфікаційної роботи студента групи 42-ІПЗ Павловича Васися\n")

def main() -> None:
    application = Application.builder().token("7699287813:AAEyWJ7LJ9jn_9wvBxV-fQZ_fy1Y-QjeHUU").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("account", account.account))
    application.add_handler(CallbackQueryHandler(account.button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, account.handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()