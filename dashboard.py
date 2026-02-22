import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from binance.client import Client
import ta

client = Client()

st.set_page_config(page_title="Breakout AI Pro", layout="wide")
st.title("🚀 Breakout Trading AI - Full Futures System")

# =====================================================
# ANALİZ FONKSİYONU
# =====================================================

def analyze_coin(symbol):

    score = 0

    # ===== BTC TREND =====
    klines_btc = client.get_klines(symbol="BTCUSDT", interval=Client.KLINE_INTERVAL_4HOUR, limit=200)
    df_btc = pd.DataFrame(klines_btc).iloc[:, :6]
    df_btc.columns = ['time','open','high','low','close','volume']
    df_btc[['open','high','low','close','volume']] = df_btc[['open','high','low','close','volume']].astype(float)

    df_btc['ema50'] = ta.trend.ema_indicator(df_btc['close'], window=50)
    df_btc['ema200'] = ta.trend.ema_indicator(df_btc['close'], window=200)

    btc_trend = "Yukarı" if df_btc['ema50'].iloc[-1] > df_btc['ema200'].iloc[-1] else "Aşağı"

    # ===== COIN 4H TREND =====
    klines_4h = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_4HOUR, limit=200)
    df4 = pd.DataFrame(klines_4h).iloc[:, :6]
    df4.columns = ['time','open','high','low','close','volume']
    df4[['open','high','low','close','volume']] = df4[['open','high','low','close','volume']].astype(float)

    df4['ema50'] = ta.trend.ema_indicator(df4['close'], window=50)
    df4['ema200'] = ta.trend.ema_indicator(df4['close'], window=200)

    trend = "Yukarı" if df4['ema50'].iloc[-1] > df4['ema200'].iloc[-1] else "Aşağı"

    # ===== 15M BREAKOUT =====
    klines_15m = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=200)
    df15 = pd.DataFrame(klines_15m).iloc[:, :6]
    df15.columns = ['time','open','high','low','close','volume']
    df15[['open','high','low','close','volume']] = df15[['open','high','low','close','volume']].astype(float)

    last = df15.iloc[-1]
    prev = df15.iloc[-2]

    resistance = df15['high'].rolling(20).max().iloc[-2]
    support = df15['low'].rolling(20).min().iloc[-2]

    long_break = last['close'] > resistance
    short_break = last['close'] < support

    avg_volume = df15['volume'].rolling(20).mean().iloc[-1]
    volume_spike = last['volume'] > avg_volume * 1.3

    # ===== ATR =====
    df15['atr'] = ta.volatility.average_true_range(
        df15['high'], df15['low'], df15['close'], window=14
    )
    atr = df15['atr'].iloc[-1]
    atr_mean = df15['atr'].rolling(20).mean().iloc[-1]

    entry_price = last['close']
    stop_price = entry_price - atr
    target_price = entry_price + (atr * 3)

    risk_percent = abs((entry_price - stop_price) / entry_price) * 100
    reward_percent = abs((target_price - entry_price) / entry_price) * 100

    # ===== FUNDING =====
    try:
        funding = client.futures_funding_rate(symbol=symbol, limit=1)
        funding_rate = float(funding[0]['fundingRate'])
    except:
        funding_rate = 0.0

    # ===== OPEN INTEREST =====
    try:
        oi_data = client.futures_open_interest(symbol=symbol)
        open_interest = float(oi_data['openInterest'])
        score += 10
    except:
        open_interest = 0.0

    # ===== SCORE =====
    if trend == btc_trend:
        score += 20

    if long_break or short_break:
        score += 25

    if volume_spike:
        score += 20

    if atr > atr_mean:
        score += 20

    if funding_rate > 0.01 and long_break:
        score -= 10

    if funding_rate < -0.01 and short_break:
        score -= 10

    score = max(score, 0)

    # ===== KARAR =====
    if score >= 70:
        if long_break and trend == "Yukarı" and btc_trend == "Yukarı" and funding_rate <= 0.01:
            decision = "🟢 LONG SETUP UYGUN"
        elif short_break and trend == "Aşağı" and btc_trend == "Aşağı" and funding_rate >= -0.01:
            decision = "🔴 SHORT SETUP UYGUN"
        else:
            decision = "⚠️ BEKLE – Şartlar tam uyumlu değil"
    else:
        decision = "❌ TRADE YOK"

    return {
        "btc_trend": btc_trend,
        "trend": trend,
        "score": score,
        "long_break": long_break,
        "short_break": short_break,
        "volume_spike": volume_spike,
        "funding_rate": funding_rate,
        "open_interest": open_interest,
        "entry": entry_price,
        "stop": stop_price,
        "target": target_price,
        "rr": round(reward_percent / risk_percent, 2),
        "df15": df15,
        "decision": decision
    }

# =====================================================
# MANUEL GİRİŞ
# =====================================================

symbol = st.text_input("Coin Gir (örnek: SOLUSDT)", "SOLUSDT").upper()

if st.button("Analiz Et"):

    data = analyze_coin(symbol)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("BTC Trend", data["btc_trend"])
    col2.metric("Coin Trend", data["trend"])
    col3.metric("Confidence", data["score"])
    col4.metric("R/R", data["rr"])

    st.progress(data["score"] / 100)

    st.subheader("💰 Futures Verileri")
    st.write("Funding Rate:", round(data["funding_rate"],6))
    st.write("Open Interest:", round(data["open_interest"],2))

    st.subheader("📈 Breakout")
    st.write("Long Break:", data["long_break"])
    st.write("Short Break:", data["short_break"])
    st.write("Hacim Güçlü:", data["volume_spike"])

    st.subheader("⚡ Risk Yönetimi")
    st.write("Giriş:", round(data["entry"],4))
    st.write("Stop:", round(data["stop"],4))
    st.write("Hedef:", round(data["target"],4))

    st.subheader("🧠 Karar Mekanizması")
    st.markdown(f"## {data['decision']}")

    # ===== GRAFİK =====
    fig = go.Figure(data=[go.Candlestick(
        x=data["df15"].index,
        open=data["df15"]['open'],
        high=data["df15"]['high'],
        low=data["df15"]['low'],
        close=data["df15"]['close']
    )])
    fig.update_layout(xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
