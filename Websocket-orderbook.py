import websocket
import json
import time
import threading
from prettytable import PrettyTable
import os

# Global variables for storing the latest orderbook data
bids = []
asks = []

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def format_number(num):
    try:
        return f"{float(num):.2f}"
    except ValueError:
        return num  # Return as is if it can't be converted to float

def print_orderbook():
    global bids, asks
    clear_screen()
    table = PrettyTable()
    table.field_names = ["Bids", "Price", "Asks"]
    table.align["Bids"] = "r"
    table.align["Price"] = "c"
    table.align["Asks"] = "l"

    max_rows = max(len(bids), len(asks))
    for i in range(max_rows):
        bid = bids[i] if i < len(bids) else ['', '']
        ask = asks[i] if i < len(asks) else ['', '']
        table.add_row([
            format_number(bid[1]),
            f"{format_number(bid[0])} | {format_number(ask[0])}",
            format_number(ask[1])
        ])

    print(table)
    print(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")

def on_message(ws, message):
    global bids, asks
    data = json.loads(message)
    if data.get('topic') == 'orderbook' and data.get('symbol') == 'usdt-dop':
        bids = data['data']['bids']
        asks = data['data']['asks']
        print_orderbook()

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    print("Opened connection")
    
    subscribe_message = {
        "op": "subscribe",
        "args": ["orderbook:usdt-dop"]
    }
    ws.send(json.dumps(subscribe_message))

def send_ping(ws):
    while True:
        time.sleep(30)
        ws.send(json.dumps({"op": "ping"}))

if __name__ == "__main__":
    websocket.enableTrace(False)  # Set to False to reduce noise in the console
    ws = websocket.WebSocketApp("wss://api.bitcoinrd-do-896247.hostingersite.com/stream",
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ping_thread = threading.Thread(target=send_ping, args=(ws,))
    ping_thread.daemon = True
    ping_thread.start()

    ws.run_forever()
