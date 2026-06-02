import requests
import time
import pandas as pd
import yfinance as yf
import os

# ==============================
# 🔑 TOKEN (Railway safe)
# ==============================
TOKEN = os.getenv("TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# ==============================
# 📤 SEND MESSAGE (WITH BUTTONS)
# ==============================
def send_message(chat_id, text):
    keyboard = {
        "keyboard": [
            ["📊 Signal", "📈 Status"],
            ["🧾 Active Trades", "🔄 Reset"]
        ],
        "resize_keyboard": True
    }

    try:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": keyboard
        })
    except Exception as e:
        print("Send Error:", e)

# ==============================
# 📥 GET UPDATES
# ==============================
def get_updates(offset=None):
    try:
        res = requests.get(
            f"{BASE_URL}/getUpdates",
            params={"timeout": 100, "offset": offset}
        ).json()

        return res if res.get("ok") else {"result": []}
    except:
        return {"result": []}

# ==============================
# 📊 RSI CALCULATION (FIXED)
# ==============================
def calculate_rsi(close, period=14):
    close = pd.Series(close).dropna()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.dropna()

# ==============================
# 🌍 ASSETS
# ==============================
ASSETS = {
    "EURUSD": "EURUSD=X",
    "GOLD": "GC=F",
    "BTC": "BTC-USD",
    "NAS100": "^NDX"
}

# ==============================
# 🌍 STATE
# ==============================
state = {
    asset: {
        "active": None,
        "last_rsi": None,
        "last_signal": None
    }
    for asset in ASSETS
}

chat_id_global = None

# ==============================
# 📈 GET MARKET DATA (FIXED)
# ==============================
def get_market(symbol):
    try:
        df = yf.download(symbol, period="1d", interval="5m", progress=False)

        if df is None or df.empty:
            return None, None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]

        close = pd.to_numeric(close, errors="coerce").dropna()

        if close.empty or len(close) < 20:
            return None, None

        rsi_series = calculate_rsi(close)

        if rsi_series.empty:
            return None, None

        price = float(close.iloc[-1])
        rsi = float(rsi_series.iloc[-1])

        return price, rsi

    except Exception as e:
        print("Market Error:", e)
        return None, None

# ==============================
# 🚨 SIGNAL ENGINE
# ==============================
def check_signal(asset, symbol):
    s = state[asset]

    price, rsi = get_market(symbol)
    if price is None or rsi is None:
        return None

    signal = None

    if s["last_rsi"] is not None:
        if s["last_rsi"] > 30 and rsi < 30 and s["last_signal"] != "BUY":
            signal = "BUY"
        elif s["last_rsi"] < 70 and rsi > 70 and s["last_signal"] != "SELL":
            signal = "SELL"

    s["last_rsi"] = rsi

    if signal is None:
        return None

    # TP/SL per asset
    if asset == "BTC":
        move = 100
    elif asset == "NAS100":
        move = 50
    elif asset == "GOLD":
        move = 5
    else:
        move = 0.0020

    if signal == "BUY":
        tp = round(price + move, 5)
        sl = round(price - move, 5)
    else:
        tp = round(price - move, 5)
        sl = round(price + move, 5)

    s["active"] = {
        "type": signal,
        "entry": price,
        "tp": tp,
        "sl": sl
    }

    s["last_signal"] = signal

    return f"""📊 NEW SIGNAL

Asset: {asset}
Type: {signal}

Entry: {price}
RSI: {round(rsi,2)}

TP: {tp}
SL: {sl}
"""

# ==============================
# 📊 TRACK TRADE RESULT
# ==============================
def check_trade(asset, symbol):
    s = state[asset]

    if not s["active"]:
        return None

    price, _ = get_market(symbol)
    if price is None:
        return None

    t = s["active"]

    if t["type"] == "BUY":
        if price >= t["tp"]:
            result = "WIN 🎯"
        elif price <= t["sl"]:
            result = "LOSS ❌"
        else:
            return None
    else:
        if price <= t["tp"]:
            result = "WIN 🎯"
        elif price >= t["sl"]:
            result = "LOSS ❌"
        else:
            return None

    msg = f"""📊 TRADE CLOSED

Asset: {asset}
Result: {result}

Entry: {t['entry']}
TP: {t['tp']}
SL: {t['sl']}
Price: {price}
"""

    s["active"] = None
    s["last_signal"] = None

    return msg

# ==============================
# 📋 STATUS
# ==============================
def get_status():
    return "📊 Bot running...\nScanning EURUSD, GOLD, BTC, NAS100..."

# ==============================
# 📋 ACTIVE TRADES
# ==============================
def get_active_trades():
    msg = "🧾 Active Trades:\n\n"
    empty = True

    for asset, s in state.items():
        if s["active"]:
            t = s["active"]
            msg += f"{asset} | {t['type']} @ {t['entry']}\n"
            empty = False

    return msg if not empty else "No active trades."

# ==============================
# 🤖 BOT LOOP
# ==============================
def run_bot():
    global chat_id_global

    print("🤖 Bot Running (Railway Ready)...")

    update_id = None

    while True:
        data = get_updates(update_id)

        for item in data.get("result", []):
            update_id = item["update_id"] + 1

            msg = item.get("message")
            if not msg:
                continue

            chat_id = msg["chat"]["id"]
            chat_id_global = chat_id

            text = msg.get("text", "")

            if text == "/start":
                send_message(chat_id, "🚀 Bot Started!\nSignals will be sent automatically.")

            elif "Signal" in text:
                send_message(chat_id, "📡 Auto mode is active.")

            elif "Status" in text:
                send_message(chat_id, get_status())

            elif "Active" in text:
                send_message(chat_id, get_active_trades())

            elif "Reset" in text:
                for a in state:
                    state[a] = {"active": None, "last_rsi": None, "last_signal": None}
                send_message(chat_id, "🔄 Bot reset complete.")

        if chat_id_global:
            for asset, symbol in ASSETS.items():

                signal = check_signal(asset, symbol)
                if signal:
                    send_message(chat_id_global, signal)

                result = check_trade(asset, symbol)
                if result:
                    send_message(chat_id_global, result)

        time.sleep(10)

# ==============================
# ▶ RUN
# ==============================
run_bot()
