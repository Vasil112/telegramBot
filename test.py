from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db_goods = client['goods']

# Перевірка, чи є товари в категорії "smartphones"
products = db_goods['smartphones'].find()
for product in products:
    print(product)