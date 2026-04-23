import requests
import time
import os

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("❌ Missing TOKEN or CHAT_ID")
    exit()

# ---------------- STATE ----------------
prices = []
target_price = None

wins = 0
losses = 0
total_trades = 0
total_profit = 0.0

position = None
entry_price = 0.0
entry_time = 0

last_update_id = 0

# ---------------- SETTINGS ----------------
STOP_LOSS_PCT = 0.003
TAKE_PROFIT_PCT = 0.006
MIN_HOLD_TIME = 60
COOLDOWN = 120

# ---------------- TELEGRAM ----------------
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Send error:", e)

# ---------------- PRICE ----------------
def get_price():
    try:
        url = "https://api.gold-api.com/price/XAU"
        res = requests.get(url).json()
        return float(res["price"])
    except Exception as e:
        print("Price error:", e)
        return None

# ---------------- EMA ----------------
def ema(prices, period):
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema_val = sum(prices[:period]) / period
    for price in prices[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

# ---------------- RSI ----------------
def rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains = 0
    losses = 0
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses += abs(diff)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ---------------- SIGNAL ----------------
def signal_engine(prices, rsi_val):
    ema5 = ema(prices, 5)
    ema10 = ema(prices, 10)
    ema20 = ema(prices, 20)

    if not ema5 or not ema10 or not ema20 or not rsi_val:
        return None

    if ema5 > ema10 and ema10 > ema20 and rsi_val < 45:
        return "BUY"

    if ema5 < ema10 and ema10 < ema20 and rsi_val > 55:
        return "SELL"

    return None

# ---------------- CLOSE TRADE ----------------
def close_trade(price, reason):
    global wins, losses, total_trades, total_profit
    global position, entry_price, entry_time

    if not position:
        return

    if position == "buy":
        profit = price - entry_price
    else:
        profit = entry_price - price

    total_trades += 1
    total_profit += profit

    if profit > 0:
        wins += 1
    else:
        losses += 1

    send(f"📊 Trade Closed ({reason})\nProfit: {profit:.2f}")

    position = None
    entry_price = 0
    entry_time = 0

# ---------------- DASHBOARD ----------------
def dashboard():
    if total_trades == 0:
        return "📊 No trades yet"

    winrate = (wins / total_trades) * 100

    return f"""
📊 DASHBOARD

Trades: {total_trades}
Wins: {wins}
Losses: {losses}
Winrate: {winrate:.2f}%

Profit: {total_profit:.2f}
"""

# ---------------- COMMANDS ----------------
def handle_commands():
    global last_update_id, target_price
    global wins, losses, total_trades, total_profit

    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        updates = requests.get(url).json()

        for update in updates.get("result", []):
            uid = update["update_id"]

            if uid <= last_update_id:
                continue

            last_update_id = uid
            msg = update.get("message", {}).get("text", "")

            print("Command:", msg)

            if msg == "/start":
                send("🤖 Bot is live!\nUse /price or /settarget 2000")

            elif msg == "/price":
                price = get_price()
                if price:
                    send(f"💰 Gold Price: {price:.2f}")
                else:
                    send("❌ Error fetching price")

            elif msg.startswith("/settarget"):
                try:
                    target_price = float(msg.split()[1])
                    send(f"🎯 Target set at {target_price}")
                except:
                    send("❌ Usage: /settarget 2000")

            elif msg == "/cleartarget":
                target_price = None
                send("🗑 Target cleared")

            elif msg == "/status":
                send("✅ Bot running")

            elif msg == "/dashboard":
                send(dashboard())

            elif msg == "/reset":
                wins = losses = total_trades = 0
                total_profit = 0
                send("🔄 Reset done")

    except Exception as e:
        print("Command error:", e)

# ---------------- MAIN LOOP ----------------
print("Bot started...")
send("🚀 Bot Online (Railway)")

last_signal_time = 0

while True:
    price = get_price()

    if price:
        prices.append(price)

        # -------- TARGET ALERT --------
        if target_price and price >= target_price:
            send(f"🚨 TARGET HIT!\nPrice: {price:.2f}")
            target_price = None

        # -------- SIGNAL --------
        if len(prices) > 50:
            rsi_val = rsi(prices)
            signal = signal_engine(prices, rsi_val)

            if position is None and signal:
                if time.time() - last_signal_time > COOLDOWN:
                    position = signal.lower()
                    entry_price = price
                    entry_time = time.time()
                    last_signal_time = time.time()
                    send(f"📌 {signal} @ {price:.2f}")

        # -------- RISK --------
        if position:
            pnl = (price - entry_price) if position == "buy" else (entry_price - price)
            pnl_pct = pnl / entry_price

            hold_time = time.time() - entry_time

            if pnl_pct <= -STOP_LOSS_PCT:
                close_trade(price, "STOP LOSS")

            elif pnl_pct >= TAKE_PROFIT_PCT:
                close_trade(price, "TAKE PROFIT")

    handle_commands()
    time.sleep(5)
