from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe
import requests
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
INTERAKT_API_KEY = os.getenv('INTERAKT_API_KEY')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
stripe.api_key = STRIPE_API_KEY

def load_catalog():
    catalog_df = pd.read_csv('product_catalog.csv')
    return catalog_df.set_index('ID').to_dict(orient='index')

PRODUCT_CATALOG = load_catalog()

DELIVERY_CHARGES = {
    "Abu Dhabi": 3500,
    "Ras Al Khaimah": 3500,
    "Fujairah": 3500,
    "Dubai": 2500,
    "Sharjah": 2000,
    "Ajman": 2000,
    "Umm Al Quwain": 2000
}

def calculate_total(product_id, quantity, location):
    product = PRODUCT_CATALOG.get(product_id)
    if not product:
        return None
    subtotal = int(product['price']) * quantity
    delivery_charge = DELIVERY_CHARGES.get(location, 0)
    total = subtotal + delivery_charge
    return total

def create_stripe_checkout_session(total, product_name, quantity):
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'aed',
                'unit_amount': total,
                'product_data': {
                    'name': f"{product_name} x {quantity}",
                },
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url='https://www.vocca.co/?srsltid=AfmBOor8qiNYFlvlvTKmhHrcye4J-4bMnWuN8Il5kuqHXy_dQRgR71J3',
        cancel_url='https://www.vocca.co/?srsltid=AfmBOor8qiNYFlvlvTKmhHrcye4J-4bMnWuN8Il5kuqHXy_dQRgR71J3',
    )
    return checkout_session.url

def send_whatsapp_message(phone_number, customer_name, order_number, total, payment_link):
    headers = {
        'Authorization': f'Basic {INTERAKT_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        "countryCode": "+971",
        "phoneNumber": phone_number,
        "type": "Template",
        "template": {
            "name": "payment_link",
            "languageCode": "en",
            "bodyValues": [
                customer_name,
                order_number,
                f"{total / 100:.2f}",
                payment_link
            ]
        }
    }
    try:
        response = requests.post('https://api.interakt.ai/v1/public/message/', headers=headers, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send WhatsApp message: {e}")
        return False

@app.route('/')
def home():
    return "Welcome to the Flask Stripe App!"  

@app.route('/favicon.ico')
def favicon():
    return '', 204  

@app.route('/api/products', methods=['GET'])
def get_products():
    return jsonify(PRODUCT_CATALOG)

@app.route('/api/process-order', methods=['POST'])
def process_order():
    data = request.json
    product_id = data['product_id']
    quantity = int(data['quantity'])
    location = data['location']
    phone = data['phone']
    customer_name = data['customer_name']

    total = calculate_total(product_id, quantity, location)
    if total is None:
        return jsonify({"error": "Invalid product ID"}), 400

    product_name = PRODUCT_CATALOG[product_id]['title']
    checkout_url = create_stripe_checkout_session(total * 100, product_name, quantity)

    order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    send_whatsapp_message(phone, customer_name, order_number, total, checkout_url)

    return jsonify({
        "message": "Order processed successfully",
        "order_number": order_number,
        "total": total,
        "checkout_url": checkout_url
    })


@app.route('/success')
def success():
    return "Payment successful."

@app.route('/cancel')
def cancel():
    return "Payment cancelled."

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
