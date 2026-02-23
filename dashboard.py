import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import ta
import threading
import time
import numpy as np

st.set_page_config(page_title="Breakout AI PRO", layout="wide")
st.title("🚀 Breakout AI - Futures Edge Edition")

# ===============================
# TELEGRAM
# ===============================

def send_telegram(message):
    token = st.secrets["TELEGRAM_TOKEN"]
    chat_id = st.secrets["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message})


# ===============================
# KUCOIN DATA
# ===============================

def get_klines(symbol, interval):
    interval_map = {
        "15m": "15min",
        "4h": "4hour"
    }

    url = "https://api.kucoin.com/api/v1/market/candles"
    params = {"type": interval_map[interval], "symbol": symbol}

    r = requests.get(url, params=params)
    data = r.json()["data"]

    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time","open","close","high","low","volume"]
    df = df.astype(float)
    df = df.sort_values("time")

    return df


def get_funding(symbol):
    try:
        url = "https://api-futures.kucoin.com/api/v1/contracts/" + symbol
        r = requests.get(url)
        data = r.json()["data"]
        return float(data["fundingFeeRate"])
    except:
        return 0.0


def get_open_interest(symbol):
    try:
        url = f"https://api-futures.kucoin.com/api/v1/openInterest?symbol={symbol}"
        r = requests.get(url)
        data = r.json()["data"]
        return float(data["value"])
    except:
        return 0.0


# ===============================
# ANALYZE
# ===============================

def analyze(symbol, volume_mult, atr_mult, threshold):

    score = 0

    df4 = get_klines(symbol, "4h")
    df15 = get_klines(symbol, "15m")

    df4["ema50"] = ta.trend.ema_indicator(df4["close"], window=50)
    df4["ema200"] = ta.trend.ema_indicator(df4["close"], window=200)

    trend_up = df4["ema50"].iloc[-1] > df4["ema200"].iloc[-1]

    last = df15.iloc[-1]
    prev = df15.iloc[-2]

    resistance = df15["high"].rolling(20).max().iloc[-2]
    support = df15["low"].rolling(20).min().iloc[-2]

    long_break = last["close"] > resistance
    short_break = last["close"] < support

    avg_volume = df15["volume"].rolling(20).mean().iloc[-1]
    volume_spike = last["volume"] > avg_volume * volume_mult

    df15["atr"] = ta.volatility.average_true_range(
        df15["high"], df15["low"], df15["close"], window=14
    )

    atr = df15["atr"].iloc[-1]
    atr_mean = df15["atr"].rolling(20).mean().iloc[-1]

    entry = last["close"]
    stop = entry - (atr * atr_mult)
    target = entry + (atr * atr_mult * 3)

    risk = abs((entry - stop) / entry) * 100
    reward = abs((target - entry) / entry) * 100

    # ===== SCORING =====
    if long_break or short_break:
        score += 30

    if volume_spike:
        score += 25

    if atr > atr_mean:
        score += 20

    if trend_up:
        score += 15

    # ===== FUNDING & OI =====
    funding = get_funding(symbol)
    oi = get_open_interest(symbol)

    if abs(funding) < 0.01:
        score += 10
    else:
        score -= 5

    if oi > 0:
        score += 5

    score = min(max(score, 0), 100)

    decision = None
    if score >= threshold and long_break:
        decision = "LONG"
    elif score >= threshold and short_break:
        decision = "SHORT"

    return score, decision, entry, stop, target, df15, funding, oi


# ===============================
# BACKTEST
# ===============================

def backtest(symbol, volume_mult, atr_mult):

    df = get_klines(symbol, "15m")

    wins = 0
    losses = 0

    df["atr"] = ta.volatility.average_true_range(
        df["high"], df["low"], df["close"], window=14
    )

    for i in range(50, len(df)-10):

        resistance = df["high"].iloc[i-20:i].max()
        close = df["close"].iloc[i]

        if close > resistance:

            entry = close
            atr = df["atr"].iloc[i]
            stop = entry - atr
            target = entry + atr * 3

            future = df.iloc[i+1:i+10]

            if future["high"].max() >= target:
                wins += 1
            elif future["low"].min() <= stop:
                losses += 1

    total = wins + losses
    winrate = (wins/total)*100 if total > 0 else 0

    return wins, losses, round(winrate,2)


# ===============================
# UI
# ===============================

st.sidebar.header("⚙ Ayarlar")

coin_input = st.sidebar.text_area(
    "Taranacak Coinler",
    "BTC-USDT,ETH-USDT,SOL-USDT"
)

threshold = st.sidebar.slider("Score Threshold", 50, 90, 75)
volume_mult = st.sidebar.slider("Hacim Çarpanı", 1.0, 3.0, 1.3)
atr_mult = st.sidebar.slider("ATR Çarpanı", 0.5, 3.0, 1.0)

COINS = [c.strip().upper() for c in coin_input.split(",")]

# ===============================
# MANUEL ANALİZ
# ===============================

symbol = st.text_input("Manuel Analiz", "BTC-USDT")

if st.button("Analiz Et"):

    score, decision, entry, stop, target, df, funding, oi = analyze(
        symbol, volume_mult, atr_mult, threshold
    )

    st.metric("Confidence", score)

    st.write("Funding:", funding)
    st.write("Open Interest:", oi)

    if decision:
        st.success(f"{decision} SETUP UYGUN")
    else:
        st.warning("Trade Yok")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close']
    )])

    fig.update_layout(xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)


# ===============================
# BACKTEST BUTTON
# ===============================

if st.button("Backtest Yap"):

    wins, losses, winrate = backtest(symbol, volume_mult, atr_mult)

    st.subheader("📊 Backtest Sonucu")
    st.write("Kazanan:", wins)
    st.write("Kaybeden:", losses)
    st.write("Winrate %:", winrate)
