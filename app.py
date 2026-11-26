import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timezone

st.set_page_config(page_title="BG AI CRYPTO TRADER", page_icon="₿", layout="wide")

st.title("₿ BG AI CRYPTO TRADER")
st.caption("BTC Spot • Automatic Paper Trading • No real orders")

st.warning("यह केवल Paper Trading है। Coinbase का सार्वजनिक BTC-USD Market Data पढ़ा जाता है; कोई Exchange Account, API Key या असली BUY/SELL Order नहीं। यह ऐप 24×7 background में नहीं चलता—Streamlit खुला होना और Scan/Refresh चलाना जरूरी है।")

STARTING_INR = 5000.0
RISK_PER_TRADE_INR = 25.0
DAILY_LOSS_LIMIT_INR = 50.0

@st.cache_data(ttl=25)
def get_btc_data():
    headers = {"User-Agent": "BG-AI-CRYPTO-TRADER/1.0"}
    now = int(time.time())
    start = now - 300 * 300
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    r = requests.get(url, params={"granularity": 300, "start": start, "end": now}, headers=headers, timeout=15)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list) or len(rows) < 40:
        raise ValueError("Coinbase से पर्याप्त BTC candles नहीं मिले। थोड़ी देर बाद फिर कोशिश करें।")
    df = pd.DataFrame(rows, columns=["time","low","high","open","close","volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    for c in ["low","high","open","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return df

@st.cache_data(ttl=60)
def get_inr_rate(btc_usd):
    # Estimate USD/INR from BTC/INR and BTC/USD public prices.
    url = "https://api.coingecko.com/api/v3/simple/price"
    r = requests.get(url, params={"ids":"bitcoin","vs_currencies":"inr"}, headers={"User-Agent":"BG-AI-CRYPTO-TRADER/1.0"}, timeout=12)
    r.raise_for_status()
    btc_inr = float(r.json()["bitcoin"]["inr"])
    return btc_inr / float(btc_usd)

def indicators(df):
    d = df.copy()
    d["ema9"] = d["close"].ewm(span=9, adjust=False).mean()
    d["ema21"] = d["close"].ewm(span=21, adjust=False).mean()
    delta = d["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi"] = 100 - (100 / (1 + rs))
    d["atr"] = pd.concat([
        d["high"]-d["low"],
        (d["high"]-d["close"].shift()).abs(),
        (d["low"]-d["close"].shift()).abs()
    ], axis=1).max(axis=1).rolling(14).mean()
    return d

if "cash" not in st.session_state:
    st.session_state.cash = STARTING_INR
    st.session_state.position = None
    st.session_state.trades = []
    st.session_state.last_scan = None
    st.session_state.day_pnl = 0.0

def close_position(price_inr, reason, timestamp):
    p = st.session_state.position
    if not p:
        return
    pnl = (price_inr - p["entry"]) * p["btc_qty"]
    st.session_state.cash += p["stake"] + pnl
    st.session_state.day_pnl += pnl
    st.session_state.trades.append({
        "Entry Time": p["time"], "Exit Time": timestamp,
        "Side": "BUY BTC", "Entry ₹": round(p["entry"],2),
        "Exit ₹": round(price_inr,2), "Stake ₹": round(p["stake"],2),
        "P&L ₹": round(pnl,2), "Reason": reason
    })
    st.session_state.position = None

col1, col2, col3 = st.columns(3)
col1.metric("Virtual Cash", f"₹{st.session_state.cash:,.2f}")
col2.metric("Daily Realized P&L", f"₹{st.session_state.day_pnl:,.2f}")
col3.metric("Open Position", "YES" if st.session_state.position else "NO")

st.subheader("Market & Strategy")
st.write("Data: Coinbase BTC-USD 5-minute candles. Signal: EMA 9/21 + RSI filter. Paper BUY only; no short selling or leverage.")
if st.button("🔄 Fetch Live BTC Data & Scan", type="primary", use_container_width=True):
    try:
        raw = get_btc_data()
        d = indicators(raw)
        last = d.iloc[-1]
        price_usd = float(last["close"])
        fx = get_inr_rate(price_usd)
        price_inr = price_usd * fx
        st.session_state.last_scan = {
            "df": d, "usd": price_usd, "fx": fx, "inr": price_inr,
            "rsi": float(last["rsi"]), "ema9": float(last["ema9"]),
            "ema21": float(last["ema21"]), "atr": float(last["atr"]),
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        st.success("Market data updated.")
    except Exception as e:
        st.error(f"Market data नहीं मिल पाया: {e}")

scan = st.session_state.last_scan
if scan:
    a,b,c,dcol = st.columns(4)
    a.metric("BTC Price (approx INR)", f"₹{scan['inr']:,.0f}")
    b.metric("BTC/USD", f"${scan['usd']:,.2f}")
    c.metric("RSI (14)", f"{scan['rsi']:.1f}")
    dcol.metric("USD/INR (estimated)", f"{scan['fx']:.2f}")
    st.caption(f"Last fetched: {scan['time']} • INR price is estimated using public BTC/INR and BTC/USD prices; FX and feed differences may occur.")

    signal = "WAIT"
    if scan["ema9"] > scan["ema21"] and 50 <= scan["rsi"] <= 68:
        signal = "BUY SETUP"
    elif scan["ema9"] < scan["ema21"] or scan["rsi"] > 75:
        signal = "EXIT / NO BUY"
    st.subheader(f"AI Rule Signal: {signal}")
    st.write(f"EMA9: ${scan['ema9']:,.2f} | EMA21: ${scan['ema21']:,.2f}")

    p = st.session_state.position
    if p:
        current = scan["inr"]
        sl = p["entry"] * 0.99
        target = p["entry"] * 1.02
        st.info(f"Open BTC paper position • Entry ₹{p['entry']:,.2f} • Stop ₹{sl:,.2f} • Target ₹{target:,.2f}")
        if current <= sl:
            close_position(current, "Stop Loss", scan["time"])
            st.error("Paper SELL: Stop Loss hit.")
        elif current >= target:
            close_position(current, "Target", scan["time"])
            st.success("Paper SELL: Target hit.")
        elif signal == "EXIT / NO BUY":
            close_position(current, "EMA/RSI exit", scan["time"])
            st.warning("Paper SELL: Exit condition.")
        else:
            st.write(f"Unrealized P&L: ₹{(current-p['entry'])*p['btc_qty']:,.2f}")
    else:
        if signal == "BUY SETUP" and st.session_state.day_pnl > -DAILY_LOSS_LIMIT_INR:
            stake = min(1000.0, st.session_state.cash)
            risk_budget = min(RISK_PER_TRADE_INR, stake)
            stop_distance = scan["inr"] * 0.01
            qty = risk_budget / stop_distance
            actual_stake = qty * scan["inr"]
            if actual_stake <= st.session_state.cash:
                st.session_state.cash -= actual_stake
                st.session_state.position = {
                    "entry": scan["inr"], "btc_qty": qty,
                    "stake": actual_stake, "time": scan["time"]
                }
                st.success(f"Automatic PAPER BUY executed • BTC quantity {qty:.8f} • Virtual stake ₹{actual_stake:,.2f}")
            else:
                st.warning("Virtual cash कम है; कोई trade नहीं लिया।")
        else:
            st.info("अभी Paper BUY नहीं हुआ। AI नियमों के अनुसार WAIT करना भी सही निर्णय है।")

    st.line_chart(scan["df"].set_index("time")[["close","ema9","ema21"]].tail(100))
else:
    st.info("पहली बार ऊपर का Fetch Live BTC Data & Scan बटन दबाएँ। ऐप पहले डेटा की उपलब्धता जाँचेगा।")

st.subheader("Risk Rules")
st.write(f"- Starting virtual capital: ₹{STARTING_INR:,.0f}")
st.write(f"- Risk budget per trade: अधिकतम ₹{RISK_PER_TRADE_INR:.0f} (1% price stop)")
st.write(f"- Daily realized loss stop: ₹{DAILY_LOSS_LIMIT_INR:.0f}")
st.write("- Target: 2% price rise; Stop Loss: 1% price fall.")
st.write("- Spot-style long only; no leverage, no short selling, no real orders.")
st.caption("यह शुरुआती नियम-आधारित Paper Simulator है, लाभ की गारंटी या निवेश सलाह नहीं। Coinbase और CoinGecko public feeds की उपलब्धता/क्षेत्रीय पहुँच बदल सकती है। यह लगातार 24×7 unattended bot नहीं है; Streamlit Cloud sleep/restart होने पर session data मिट सकता है।")

st.subheader("Paper Trade History")
if st.session_state.trades:
    st.dataframe(pd.DataFrame(st.session_state.trades), use_container_width=True, hide_index=True)
else:
    st.write("अभी कोई बंद Paper Trade नहीं है।")

if st.button("Reset Paper Account"):
    st.session_state.cash = STARTING_INR
    st.session_state.position = None
    st.session_state.trades = []
    st.session_state.last_scan = None
    st.session_state.day_pnl = 0.0
    st.rerun()
