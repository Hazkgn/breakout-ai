import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import ta

st.set_page_config(page_title="Breakout AI Pro", layout="wide")
st.title("🚀 Breakout Trading AI - Cloud Version")

# ==============================
# KUCOIN DATA FUNCTIONS
# ==============================

def get_klines(symbol, interval):
    interval_map = {
        "15m": "15min",
        "1h": "1hour",
        "4h": "4hour"
    }

    url = f"https://api.kucoin.com/api/v1/market/candles"
    params = {
        "type": interval_map[interval],
        "symbol": symbol,
    }

    response = requests.get(url, params=params)
    data = response.json()["data"]

    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time","open","close","high","low","volume"]
    df = df.astype(float)
    df = df.sort_values("time")

    return df


# ==============================
# ANALYZE FUNCTION
# ==============================

def analyze(symbol):

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
    volume_spike = last["volume"] > avg_volume * 1.3

    df15["atr"] = ta.volatility.average_true_range(
        df15["high"], df15["low"], df15["close"], window=14
    )

    atr = df15["atr"].iloc[-1]
    atr_mean = df15["atr"].rolling(20).mean().iloc[-1]

    entry = last["close"]
    stop = entry - atr
    target = entry + (atr * 3)

    risk = abs((entry - stop) / entry) * 100
    reward = abs((target - entry) / entry) * 100

    # SCORE
    if long_break or short_break:
        score += 30

    if volume_spike:
        score += 25

    if atr > atr_mean:
        score += 20

    if trend_up:
        score += 15

    score = min(score, 100)

    # DECISION
    if score >= 75 and long_break:
        decision = "🟢 LONG SETUP UYGUN"
    elif score >= 75 and short_break:
        decision = "🔴 SHORT SETUP UYGUN"
    elif score >= 60:
        decision = "⚠️ BEKLE"
    else:
        decision = "❌ TRADE YOK"

    return {
        "score": score,
        "decision": decision,
        "entry": entry,
        "stop": stop,
        "target": target,
        "rr": round(reward / risk, 2),
        "df": df15
    }


# ==============================
# UI
# ==============================

symbol = st.text_input("KuCoin Symbol (örn: BTC-USDT)", "BTC-USDT")

if st.button("Analiz Et"):

    data = analyze(symbol)

    col1, col2 = st.columns(2)

    col1.metric("Confidence", data["score"])
    col2.metric("R/R", data["rr"])

    st.progress(data["score"] / 100)

    st.subheader("🧠 Karar")
    st.markdown(f"## {data['decision']}")

    st.subheader("⚡ Risk")
    st.write("Entry:", round(data["entry"],4))
    st.write("Stop:", round(data["stop"],4))
    st.write("Target:", round(data["target"],4))

    fig = go.Figure(data=[go.Candlestick(
        x=data["df"].index,
        open=data["df"]['open'],
        high=data["df"]['high'],
        low=data["df"]['low'],
        close=data["df"]['close']
    )])

    fig.update_layout(xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
