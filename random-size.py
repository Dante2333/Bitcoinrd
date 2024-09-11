import requests
import random
import time
import hmac
import hashlib
import json
from datetime import datetime
from telebot.types import Message
import telebot
import logging


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def stringify_body(body):
    if body:
        return json.dumps(body, separators=(',', ':'))
    return ''
# Configuration
API_URL = "https://api.bitcoinrd.do/v2"
API_KEY = "your_key"
API_SECRET = "your_secret"
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"
TELEGRAM_CHAT_ID = "Your_telegram_ID"
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

SYMBOL = "usdt-dop"
DEFAULT_MID_PRICE = 58
USE_DEFAULT_PRICE = True
UPDATE_INTERVAL = 600  # Update orders every 60 seconds

#New order level configuration
NUMBER_OF_LEVELS = 5
SPREAD_PER_LEVEL = 0.0090
TOTAL_BALANCE_PERCENTAGE = 0.99

import random

def update_orders():
    if USE_DEFAULT_PRICE:
        mid_price = DEFAULT_MID_PRICE
        logger.info(f"Using default mid-price: {mid_price}")
    else:
        orderbook = get_orderbook()
        if not orderbook:
            logger.error("Failed to update orders: couldn't get orderbook")
            return
        best_bid = float(orderbook['bids'][0][0])
        best_ask = float(orderbook['asks'][0][0])
        mid_price = (best_bid + best_ask) / 2
        logger.info(f"Using orderbook mid-price: {mid_price}")

    usdt_balance, dop_balance = get_portfolio_balance()
    if usdt_balance is None or dop_balance is None:
        logger.error("Failed to update orders: couldn't get balance")
        return

    logger.info(f"Current balances - USDT: {usdt_balance}, DOP: {dop_balance}")

    cancel_all_orders()
    
    usdt_to_use = usdt_balance * TOTAL_BALANCE_PERCENTAGE
    dop_to_use = dop_balance * TOTAL_BALANCE_PERCENTAGE

    buy_orders = []
    sell_orders = []

    for i in range(NUMBER_OF_LEVELS):
        buy_price = round(mid_price * (1 - (i + 1) * SPREAD_PER_LEVEL), 2)
        sell_price = round(mid_price * (1 + (i + 1) * SPREAD_PER_LEVEL), 2)
        
        buy_orders.append(buy_price)
        sell_orders.append(sell_price)

    # Generate random sizes for buy orders (in DOP)
    buy_sizes_dop = [random.uniform(0, dop_to_use) for _ in range(NUMBER_OF_LEVELS)]
    total_buy_size_dop = sum(buy_sizes_dop)
    buy_sizes_dop = [size * dop_to_use / total_buy_size_dop for size in buy_sizes_dop]

    # Generate random sizes for sell orders (in USDT)
    sell_sizes_usdt = [random.uniform(0, usdt_to_use) for _ in range(NUMBER_OF_LEVELS)]
    total_sell_size_usdt = sum(sell_sizes_usdt)
    sell_sizes_usdt = [size * usdt_to_use / total_sell_size_usdt for size in sell_sizes_usdt]

    successful_orders = 0

    for i in range(NUMBER_OF_LEVELS):
        # Buy order
        buy_price = buy_orders[i]
        buy_size_dop = buy_sizes_dop[i]
        buy_size_usdt = round(buy_size_dop / buy_price, 2)  # Convert DOP to USDT
        logger.info(f"Placing buy order - Price: {buy_price}, Size (USDT): {buy_size_usdt}, (DOP: {buy_size_dop})")
        buy_order = place_order("buy", buy_price, buy_size_usdt)
        if buy_order:
            successful_orders += 1

        # Sell order
        sell_price = sell_orders[i]
        sell_size_usdt = round(sell_sizes_usdt[i], 2)
        logger.info(f"Placing sell order - Price: {sell_price}, Size (USDT): {sell_size_usdt}")
        sell_order = place_order("sell", sell_price, sell_size_usdt)
        if sell_order:
            successful_orders += 1

    total_orders = NUMBER_OF_LEVELS * 2
    if successful_orders == total_orders:
        logger.info("Successfully updated all orders")
    else:
        logger.warning(f"Placed {successful_orders} out of {total_orders} orders")

    # Log remaining balances
    remaining_usdt, remaining_dop = get_portfolio_balance()
    logger.info(f"Remaining balances - USDT: {remaining_usdt}, DOP: {remaining_dop}")

def get_portfolio_balance():
    balance = make_request("GET", "/user/balance")
    if balance:
        usdt_balance = float(balance.get('usdt_available', 0))
        dop_balance = float(balance.get('dop_available', 0))
        logger.info(f"Current Balance - USDT: {usdt_balance}, DOP: {dop_balance}")
        return usdt_balance, dop_balance
    logger.error("Failed to fetch balance")
    return None, None

def round_to_increment(value, increment):
    return round(value / increment) * increment

# Initialize Telegram bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def send_telegram_message(message):
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f"Telegram message sent: {message}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

def generate_signature(method, endpoint, expires, body=None):
    path = f"/v2{endpoint}"
    message = f"{method}{path}{expires}{stringify_body(body)}"
    logger.info(f"Message to sign: {message}")
    signature = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    logger.info(f"Generated signature: {signature}")
    return signature

def make_request(method, endpoint, body=None):
    try:
        expires = str(int(time.time()) + 60)  # Set expiry to 60 seconds from now
        signature = generate_signature(method, endpoint, expires, body)
        headers = {
            'api-key': API_KEY,
            'api-signature': signature,
            'api-expires': expires,
            'Content-Type': 'application/json'
        }
        url = f"{API_URL}{endpoint}"
        logger.info(f"Making request: {method} {url}")
        logger.info(f"Headers: {headers}")
        if body:
            logger.info(f"Body: {stringify_body(body)}")
        response = requests.request(method, url, headers=headers, json=body)
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response content: {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None

def get_orderbook():
    response = make_request("GET", f"/orderbook?symbol={SYMBOL}")
    if response and SYMBOL in response:
        return response[SYMBOL]
    logger.error("Failed to get orderbook")
    return None

def place_order(side, price, size):
    body = {
        "symbol": SYMBOL,
        "side": side,
        "size": size,
        "type": "limit",
        "price": price
    }
    
    logger.info(f"Attempting to place {side} order: Size (USDT): {size}, Price: {price}")
    response = make_request("POST", "/order", body)
    if response and 'id' in response:
        logger.info(f"Successfully placed {side} order: ID: {response['id']}, Size (USDT): {size}, Price: {price}")
        send_telegram_message(f"Placed {side} order: Size (USDT): {size}, Price: {price}")
        return response
    logger.error(f"Failed to place {side} order: {response}")
    return None

def cancel_all_orders():
    response = make_request("DELETE", f"/order/all?symbol={SYMBOL}")
    if response:
        logger.info("Cancelled all orders")
        send_telegram_message("Cancelled all orders")
        return response
    logger.error("Failed to cancel orders")
    time.sleep(10)
    return None


@bot.message_handler(commands=['update_price'])
def handle_update_price(message: Message):
    try:
        _, new_price = message.text.split()
        new_price = float(new_price)
        update_mid_price(new_price)
        bot.reply_to(message, f"Mid-price updated to {new_price}")
    except ValueError:
        bot.reply_to(message, "Invalid price format. Use /update_price <new_price>")

def update_mid_price(new_price):
    global DEFAULT_MID_PRICE
    DEFAULT_MID_PRICE = new_price
    logger.info(f"Updated default mid-price to: {DEFAULT_MID_PRICE}")
    send_telegram_message(f"Updated default mid-price to: {DEFAULT_MID_PRICE}")

def initialize_portfolio():
    logger.info("Initializing portfolio")
    send_telegram_message("Bot started. Fetching initial portfolio balance.")
    get_portfolio_balance()  # This will log the actual balance

import threading

def main():
    last_price_update = datetime.now().date()

    # Start the bot polling in a separate thread
    bot_thread = threading.Thread(target=bot.polling, kwargs={"none_stop": True})
    bot_thread.start()

    while True:
        try:
            current_date = datetime.now().date()
            if current_date > last_price_update:
                logger.info("New day started. Please update the mid-price if needed.")
                send_telegram_message("New day started. Please update the mid-price if needed.")
                last_price_update = current_date

            update_orders()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            send_telegram_message(f"Error in main loop: {str(e)}")
        finally:
            time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    logger.info("Market Maker Bot started")
    send_telegram_message("Market Maker Bot started")
    main()
