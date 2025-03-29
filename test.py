import requests

invoice_id = "2503275K9JFbT8cgWKAT"  # Ваш invoiceId
token = "uxknxd8adVw1__oXS0CDXVQcnkwOIG4uk0CYYT74_TYg"

headers = {
    "X-Token": token,
    "Content-Type": "application/json"
}

url = f"https://api.monobank.ua/api/merchant/invoice/status?invoiceId={invoice_id}"
response = requests.get(url, headers=headers)

print(response.status_code, response.json())



application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
#має бути у bot.py у фукнції main()