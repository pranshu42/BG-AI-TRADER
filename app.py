import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timezone, date

st.set_page_config(page_title="BG AI CRYPTO TRADER", page_icon="₿", layout="wide")
st.title("₿ BG AI CRYPTO TRADER")
st.caption("BTC Spot • Automatic Paper Trading • No real orders")

st.warning(
    "यह केवल Paper Trading है। Coinbase का सार्वजनिक BTC-USD डेटा पढ़ा जाता है। "
    "कोई Exchange Account/API Key या असली BUY/SELL Order नहीं। ऐप 24×7 background में नहीं चलता; "
    "Scan/Refresh करना जरूरी है। Streamlit restart होने पर session वाला Paper Account reset हो सकता है।"
)

STARTING_INR = 5000.0
RISK_PER_TRADE_INR = 25.0
DAILY_LOSS_LIMIT_INR = 50.0
MAX_STAKE_INR = 2500.0
STOP_LOSS_PCT = 0.01
TARGET_PCT = 0.02

@st.cache_data(ttl=25)
def get_btc_data():
    headers = {"User-Agent": "BG-AI-CRYPTO-TRADER/1.1"}
    now = int(time.time())
    start = now - 300 * 300
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    response = requests.get(
        url,
        params={"granularity": 300, "start": start, "end": now},
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list) or len(rows) < 40:
        raise ValueError("Coinbase से पर्याप्त BTC candles नहीं मिले। थोड़ी देर बाद फिर कोशिश करें।")
    frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    for column in ["low", "high", "open", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("time").drop_duplicates("time").reset_index(drop=True)

@st.cache_data(ttl=60)
def get_inr_rate(btc_usd):
    url = "https://api.coingecko.com/api/v3/simple/price"
    response = requests.get(
        url,
        params={"ids": "bitcoin", "vs_currencies": "inr"},
        headers={"User-Agent": "BG-AI-CRYPTO-TRADER/1.1"},
        timeout=12,
    )
    response.raise_for_status()
    btc_inr = float(response.json()["bitcoin"]["inr"])
    return btc_inr / float(btc_usd)

def add_indicators(frame):
    data = frame.copy()
    data["ema9"] = data["close"].ewm(span=9, adjust=False).mean()
    data["ema21"] = data["close"].ewm(span=21, adjust=False).mean()
    delta = data["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    data["rsi"] = 100 - (100 / (1 + rs))
    data["rsi"] = data["rsi"].fillna(50)
    return data

# Initialize account state once per Streamlit session.
if "account_initialized" not in st.session_state:
    st.session_state.account_initialized = True
    st.session_state.cash = STARTING_INR
    st.session_state.position = None
    st.session_state.trades = []
    st.session_state.last_scan = None
    st.session_state.day_pnl = 0.0
    st.session_state.pnl_date = date.today().isoformat()
    st.session_state.notice = "पहली बार ऊपर का Scan बटन दबाएँ।"

# Reset realized daily P&L when the calendar date changes.
today = date.today().isoformat()
if st.session_state.pnl_date != today:
    st.session_state.pnl_date = today
    st.session_state.day_pnl = 0.0

st.subheader("Market & Strategy")
st.write("Data: Coinbase BTC-USD 5-minute candles. Strategy: EMA 9/21 + RSI filter. Long-only paper trades; no leverage.")

if st.button("🔄 Fetch Live BTC Data & Scan", type="primary", use_container_width=True):
    try:
        raw = get_btc_data()
        data = add_indicators(raw)
        last = data.iloc[-1]
        price_usd = float(last["close"])
        fx = get_inr_rate(price_usd)
        price_inr = price_usd * fx
        if not np.isfinite(price_inr) or price_inr <= 0:
            raise ValueError("BTC INR कीमत सही नहीं मिली।")
        st.session_state.last_scan = {
            "df": data,
            "usd": price_usd,
            "fx": fx,
            "inr": price_inr,
            "rsi": float(last["rsi"]),
            "ema9": float(last["ema9"]),
            "ema21": float(last["ema21"]),
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        st.session_state.notice = "Market data updated."
    except Exception as error:
        st.session_state.notice = f"डेटा नहीं मिला: {error}"

scan = st.session_state.last_scan

if scan:
    signal = "WAIT"
    if scan["ema9"] > scan["ema21"] and 50 <= scan["rsi"] <= 68:
        signal = "BUY SETUP"
    elif scan["ema9"] < scan["ema21"] or scan["rsi"] > 75:
        signal = "EXIT / NO BUY"

    # Manage an existing position first. Never open a second position while one is active.
    position = st.session_state.position
    if position:
        current_price = scan["inr"]
        stop_price = position["entry"] * (1 - STOP_LOSS_PCT)
        target_price = position["entry"] * (1 + TARGET_PCT)
        exit_reason = None
        if current_price <= stop_price:
            exit_reason = "Stop Loss"
        elif current_price >= target_price:
            exit_reason = "Target"
        elif signal == "EXIT / NO BUY":
            exit_reason = "EMA/RSI exit"

        if exit_reason:
            pnl = (current_price - position["entry"]) * position["btc_qty"]
            st.session_state.cash += position["stake"] + pnl
            st.session_state.day_pnl += pnl
            st.session_state.trades.append({
                "Entry Time": position["time"],
                "Exit Time": scan["time"],
                "Side": "BUY BTC",
                "Entry ₹": round(position["entry"], 2),
                "Exit ₹": round(current_price, 2),
                "Stake ₹": round(position["stake"], 2),
                "BTC Qty": round(position["btc_qty"], 8),
                "P&L ₹": round(pnl, 2),
                "Reason": exit_reason,
            })
            st.session_state.position = None
            st.session_state.notice = f"Paper SELL हुआ: {exit_reason} | P&L ₹{pnl:,.2f}"
        else:
            unrealized = (current_price - position["entry"]) * position["btc_qty"]
            st.session_state.notice = f"Position खुली है। अभी Unrealized P&L ₹{unrealized:,.2f}"

    # If flat, enter only when the rule signal is BUY and the daily loss limit allows it.
    if st.session_state.position is None and signal == "BUY SETUP":
        if st.session_state.day_pnl <= -DAILY_LOSS_LIMIT_INR:
            st.session_state.notice = "Daily loss limit पूरी हो गई; आज नया Paper BUY बंद है।"
        elif not st.session_state.trades or st.session_state.trades[-1].get("Exit Time") != scan["time"]:
            stake = min(MAX_STAKE_INR, st.session_state.cash)
            stop_distance = scan["inr"] * STOP_LOSS_PCT
            quantity = min(RISK_PER_TRADE_INR / stop_distance, stake / scan["inr"])
            actual_stake = quantity * scan["inr"]
            if actual_stake > 0 and actual_stake <= st.session_state.cash:
                st.session_state.cash -= actual_stake
                st.session_state.position = {
                    "entry": scan["inr"],
                    "btc_qty": quantity,
                    "stake": actual_stake,
                    "time": scan["time"],
                }
                st.session_state.notice = (
                    f"Automatic PAPER BUY executed • BTC quantity {quantity:.8f} "
                    f"• Virtual stake ₹{actual_stake:,.2f}"
                )
            else:
                st.session_state.notice = "Virtual cash कम है; कोई trade नहीं लिया।"
    elif st.session_state.position is None and signal != "BUY SETUP":
        st.session_state.notice = "अभी Paper BUY नहीं हुआ। नियमों के अनुसार WAIT करना भी सही निर्णय है।"

    st.success(st.session_state.notice) if "BUY executed" in st.session_state.notice else st.info(st.session_state.notice)

    # Recalculate and display account values AFTER all trade actions, fixing stale metrics.
    open_position = st.session_state.position
    unrealized_pnl = 0.0
    invested = 0.0
    if open_position:
        invested = open_position["stake"]
        unrealized_pnl = (scan["inr"] - open_position["entry"]) * open_position["btc_qty"]
    equity = st.session_state.cash + invested + unrealized_pnl

    st.subheader("Paper Account")
    m1, m2, m3 = st.columns(3)
    m1.metric("Free Virtual Cash", f"₹{st.session_state.cash:,.2f}")
    m2.metric("Open Position", "YES" if open_position else "NO")
    m3.metric("Total Virtual Equity", f"₹{equity:,.2f}")
    m4, m5, m6 = st.columns(3)
    m4.metric("Daily Realized P&L", f"₹{st.session_state.day_pnl:,.2f}")
    m5.metric("Unrealized P&L", f"₹{unrealized_pnl:,.2f}")
    m6.metric("Invested Stake", f"₹{invested:,.2f}")

    st.subheader("Live BTC Market")
    a, b, c, d = st.columns(4)
    a.metric("BTC Price (approx INR)", f"₹{scan['inr']:,.0f}")
    b.metric("BTC/USD", f"${scan['usd']:,.2f}")
    c.metric("RSI (14)", f"{scan['rsi']:.1f}")
    d.metric("USD/INR (estimated)", f"{scan['fx']:.2f}")
    st.caption(f"Last fetched: {scan['time']} • INR value estimated from public BTC/INR and BTC/USD prices.")

    st.subheader(f"AI Rule Signal: {signal}")
    st.write(f"EMA9: ${scan['ema9']:,.2f} | EMA21: ${scan['ema21']:,.2f}")
    if open_position:
        sl = open_position["entry"] * (1 - STOP_LOSS_PCT)
        target = open_position["entry"] * (1 + TARGET_PCT)
        st.write(
            f"Open BTC Paper Position • Entry ₹{open_position['entry']:,.2f} "
            f"• Stop Loss ₹{sl:,.2f} • Target ₹{target:,.2f}"
        )
    st.line_chart(scan["df"].set_index("time")[["close", "ema9", "ema21"]].tail(100))
else:
    st.info(st.session_state.notice)

st.subheader("Risk Rules")
st.write(f"- Starting virtual capital: ₹{STARTING_INR:,.0f}")
st.write(f"- Risk budget per trade: अधिकतम ₹{RISK_PER_TRADE_INR:.0f} (1% stop distance)")
st.write(f"- Daily realized loss stop: ₹{DAILY_LOSS_LIMIT_INR:.0f}")
st.write("- Target: 2% price rise; Stop Loss: 1% price fall.")
st.write("- Spot-style long only; no leverage, no short selling, no real orders.")
st.caption("यह शुरुआती नियम-आधारित Paper Simulator है, लाभ की गारंटी या निवेश सलाह नहीं। Scan दबाने पर ही नई जाँच होती है; यह 24×7 unattended bot नहीं है। Streamlit Cloud restart/sleep होने पर session data reset हो सकता है।")

st.subheader("Paper Trade History")
if st.session_state.trades:
    st.dataframe(pd.DataFrame(st.session_state.trades), use_container_width=True, hide_index=True)
else:
    st.write("अभी कोई बंद Paper Trade नहीं है।")

if st.button("Reset Paper Account"):
    for key in ["cash", "position", "trades", "last_scan", "day_pnl", "pnl_date", "notice", "account_initialized"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
