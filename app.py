import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import json
from pathlib import Path

st.set_page_config(page_title="BG AI TRADER", page_icon="📈", layout="wide")

# Educational paper-trading configuration only.
START_CAPITAL = 5000.0
RISK_PER_TRADE = 25.0
DAILY_LOSS_LIMIT = 50.0
MAX_NEW_BUYS_PER_DAY = 2
STOP_LOSS_PCT = 0.02
TARGET_PCT = 0.04
WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "SBIN.NS", "ITC.NS", "BHARTIARTL.NS",
    "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "MARUTI.NS"
]
STATE_FILE = Path("bg_ai_trader_paper_state.json")

def fresh_state():
    return {
        "cash": START_CAPITAL,
        "positions": {},
        "trades": [],
        "realized_today": 0.0,
        "trade_day": date.today().isoformat(),
        "last_scan": "अभी स्कैन नहीं हुआ",
        "scan_rows": []
    }

def load_state():
    # Local runtime file is a convenience, not guaranteed permanent cloud storage.
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            default = fresh_state()
            default.update(data)
            return default
        except Exception:
            pass
    return fresh_state()

def save_state():
    data = {
        "cash": st.session_state.cash,
        "positions": st.session_state.positions,
        "trades": st.session_state.trades,
        "realized_today": st.session_state.realized_today,
        "trade_day": st.session_state.trade_day,
        "last_scan": st.session_state.last_scan,
        "scan_rows": st.session_state.scan_rows
    }
    try:
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

if "initialized" not in st.session_state:
    saved = load_state()
    for key, value in saved.items():
        st.session_state[key] = value
    st.session_state.initialized = True

today = date.today().isoformat()
if st.session_state.trade_day != today:
    st.session_state.trade_day = today
    st.session_state.realized_today = 0.0
    save_state()

def as_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj

def rsi_series(close, period=14):
    delta = close.diff()
    gains = delta.clip(lower=0).rolling(period).mean()
    losses = -delta.clip(upper=0).rolling(period).mean()
    rs = gains / losses.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

def get_daily_signal(symbol):
    data = yf.download(
        symbol, period="6mo", interval="1d",
        auto_adjust=True, progress=False, threads=False
    )
    if data is None or data.empty or len(data) < 60:
        return None, "डेटा उपलब्ध नहीं / पर्याप्त इतिहास नहीं"

    close = as_series(data["Close"]).dropna()
    volume = as_series(data["Volume"]).reindex(close.index)
    if len(close) < 30:
        return None, "डेटा अधूरा"

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    rsi = rsi_series(close)
    vol_avg = volume.rolling(20).mean()

    price = float(close.iloc[-1])
    current_rsi = float(rsi.iloc[-1])
    current_volume = float(volume.iloc[-1])
    average_volume = float(vol_avg.iloc[-1]) if pd.notna(vol_avg.iloc[-1]) else 0.0

    if not all(pd.notna(x) for x in [price, current_rsi, ema9.iloc[-1], ema21.iloc[-1]]):
        return None, "इंडिकेटर डेटा अधूरा"

    volume_ok = average_volume > 0 and current_volume >= average_volume
    buy = float(ema9.iloc[-1]) > float(ema21.iloc[-1]) and 50 <= current_rsi <= 68 and volume_ok
    return {
        "price": price,
        "rsi": current_rsi,
        "signal": "BUY" if buy else "WAIT",
        "volume_ok": volume_ok
    }, "EMA9/EMA21 + RSI + 20-day volume confirmation"

def add_trade(symbol, side, qty, price, pnl=0.0, note=""):
    st.session_state.trades.append({
        "Date": date.today().isoformat(),
        "Time": datetime.now().strftime("%H:%M:%S"),
        "Symbol": symbol.replace(".NS", ""),
        "Side": side,
        "Qty": int(qty),
        "Price ₹": round(float(price), 2),
        "Realized P&L ₹": round(float(pnl), 2),
        "Note": note
    })

def close_position(symbol, price, reason):
    pos = st.session_state.positions[symbol]
    qty = int(pos["qty"])
    pnl = (float(price) - float(pos["avg"])) * qty
    st.session_state.cash += float(price) * qty
    st.session_state.realized_today += pnl
    add_trade(symbol, "SELL", qty, price, pnl, reason)
    del st.session_state.positions[symbol]

def scan_and_trade():
    scan_rows = []
    prices = {}

    for symbol in WATCHLIST:
        try:
            result, note = get_daily_signal(symbol)
            if result is None:
                scan_rows.append({
                    "Market": "India NSE", "Symbol": symbol.replace(".NS", ""),
                    "Price ₹": None, "RSI": None, "Signal": "NO DATA", "Reason": note
                })
            else:
                prices[symbol] = result["price"]
                scan_rows.append({
                    "Market": "India NSE", "Symbol": symbol.replace(".NS", ""),
                    "Price ₹": round(result["price"], 2),
                    "RSI": round(result["rsi"], 1),
                    "Signal": result["signal"], "Reason": note
                })
        except Exception as exc:
            scan_rows.append({
                "Market": "India NSE", "Symbol": symbol.replace(".NS", ""),
                "Price ₹": None, "RSI": None, "Signal": "ERROR",
                "Reason": str(exc)[:100]
            })

    # Update simulated LTP and evaluate exits on this scan only.
    for symbol in list(st.session_state.positions.keys()):
        if symbol not in prices:
            continue
        pos = st.session_state.positions[symbol]
        ltp = float(prices[symbol])
        pos["ltp"] = ltp
        if ltp <= float(pos["stop"]):
            close_position(symbol, ltp, "Paper Stop Loss")
        elif ltp >= float(pos["target"]):
            close_position(symbol, ltp, "Paper Target")

    buys_today = sum(
        1 for trade in st.session_state.trades
        if trade["Date"] == today and trade["Side"] == "BUY"
    )
    new_buys = 0
    remaining_slots = max(0, MAX_NEW_BUYS_PER_DAY - buys_today)

    if st.session_state.realized_today > -DAILY_LOSS_LIMIT:
        for row in scan_rows:
            if remaining_slots <= 0:
                break
            if row["Signal"] != "BUY" or row["Price ₹"] is None:
                continue

            symbol = row["Symbol"] + ".NS"
            if symbol in st.session_state.positions:
                continue

            entry = float(row["Price ₹"])
            stop = round(entry * (1 - STOP_LOSS_PCT), 2)
            target = round(entry * (1 + TARGET_PCT), 2)
            risk_per_share = entry - stop

            # Whole-share quantity: never exceed ₹25 planned stop-loss risk.
            qty_by_risk = int(RISK_PER_TRADE // risk_per_share) if risk_per_share > 0 else 0
            qty_by_cash = int(st.session_state.cash // entry) if entry > 0 else 0
            qty = min(qty_by_risk, qty_by_cash)

            if qty < 1:
                row["Signal"] = "WAIT"
                row["Reason"] = (
                    f"₹{RISK_PER_TRADE:.0f} risk budget में 1 शेयर भी फिट नहीं; "
                    "trade skip किया"
                )
                continue

            planned_risk = risk_per_share * qty
            if planned_risk > RISK_PER_TRADE + 0.01:
                row["Signal"] = "WAIT"
                row["Reason"] = "Risk cap से अधिक; trade skip"
                continue

            cost = qty * entry
            st.session_state.cash -= cost
            st.session_state.positions[symbol] = {
                "qty": qty, "avg": entry, "ltp": entry,
                "stop": stop, "target": target,
                "planned_risk": round(planned_risk, 2)
            }
            add_trade(symbol, "BUY", qty, entry, 0.0, "Auto Paper BUY: EMA/RSI/volume")
            new_buys += 1
            remaining_slots -= 1

    st.session_state.scan_rows = scan_rows
    st.session_state.last_scan = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    save_state()
    return new_buys

st.title("📈 BG AI TRADER")
st.caption("Version 1.3 · India NSE Only · Automatic Paper Trading · Navia Live API कनेक्ट नहीं है")
st.warning(
    "यह केवल शैक्षिक Paper Trading है। Yahoo Finance का दैनिक ऐतिहासिक डेटा "
    "विलंबित, अधूरा या अनुपलब्ध हो सकता है। कोई वास्तविक ऑर्डर नहीं भेजा जाता। "
    "स्कैन/BUY/SELL केवल बटन दबाने पर चलते हैं; 24/7 background bot नहीं है।"
)

positions = st.session_state.positions
open_value = sum(float(p["qty"]) * float(p.get("ltp", p["avg"])) for p in positions.values())
unrealized = sum(
    (float(p.get("ltp", p["avg"])) - float(p["avg"])) * int(p["qty"])
    for p in positions.values()
)
total_pnl = float(st.session_state.cash) + open_value - START_CAPITAL

cols = st.columns(4)
cols[0].metric("Virtual Capital", f"₹{START_CAPITAL:,.2f}")
cols[1].metric("Available Cash", f"₹{st.session_state.cash:,.2f}")
cols[2].metric("Open P&L", f"₹{unrealized:,.2f}")
cols[3].metric("Total Paper P&L", f"₹{total_pnl:,.2f}")

st.info(
    f"Last scan: {st.session_state.last_scan} · प्रति ट्रेड जोखिम ₹{RISK_PER_TRADE:.0f} "
    f"· दैनिक realized loss limit ₹{DAILY_LOSS_LIMIT:.0f} · "
    f"अधिकतम नए BUY/day {MAX_NEW_BUYS_PER_DAY}"
)

scanner_tab, positions_tab, history_tab, rules_tab = st.tabs([
    "🤖 NSE Auto Scanner", "📦 Positions", "📜 Trade History", "🛡️ Rules"
])

with scanner_tab:
    st.write("नियम: Daily EMA 9/21, RSI(14), और 20-day average volume confirmation.")
    st.write("BUY तभी जब EMA9 > EMA21, RSI 50–68 और आज का volume 20-day average के बराबर/ऊपर हो.")
    st.warning(
        "सिग्नल BUY होने पर भी शेयर तभी खरीदा जाएगा जब whole-share quantity "
        "₹25 risk cap और उपलब्ध cash दोनों में फिट हो। अन्यथा WAIT/skip."
    )
    if st.button("🔎 Scan NSE + Execute Paper Trades", type="primary", use_container_width=True):
        with st.spinner("NSE शेयरों का दैनिक डेटा जाँचा जा रहा है..."):
            count = scan_and_trade()
        st.success(f"स्कैन पूरा। नए Paper BUY: {count}")
    if st.session_state.scan_rows:
        st.dataframe(pd.DataFrame(st.session_state.scan_rows), use_container_width=True, hide_index=True)

with positions_tab:
    if positions:
        rows = []
        for symbol, pos in positions.items():
            ltp = float(pos.get("ltp", pos["avg"]))
            rows.append({
                "Symbol": symbol.replace(".NS", ""),
                "Qty": int(pos["qty"]),
                "Average Buy ₹": round(float(pos["avg"]), 2),
                "Latest Simulated Price ₹": round(ltp, 2),
                "Unrealized P&L ₹": round((ltp - float(pos["avg"])) * int(pos["qty"]), 2),
                "Stop Loss ₹": round(float(pos["stop"]), 2),
                "Target ₹": round(float(pos["target"]), 2),
                "Planned Risk ₹": round(float(pos.get("planned_risk", 0)), 2)
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("अभी कोई open paper position नहीं है।")

with history_tab:
    if st.session_state.trades:
        history = pd.DataFrame(st.session_state.trades)
        st.dataframe(history, use_container_width=True, hide_index=True)
        st.download_button(
            "Download Trade History CSV",
            history.to_csv(index=False).encode("utf-8"),
            "bg_ai_trader_v1_3_history.csv",
            "text/csv"
        )
    else:
        st.info("अभी कोई paper trade दर्ज नहीं है।")

with rules_tab:
    st.write("- केवल भारतीय NSE cash-equity watchlist; USA/F&O/leverage बंद.")
    st.write("- Virtual starting capital ₹5,000.")
    st.write("- प्रति ट्रेड planned stop-loss risk अधिकतम ₹25; whole-share quantity के अनुसार.")
    st.write("- दैनिक realized loss limit ₹50; अधिकतम 2 नए BUY प्रतिदिन.")
    st.write("- Stop Loss/Target अगली manual scan पर उपलब्ध daily close से जाँचे जाते हैं.")
    st.write("- BUY सिग्नल होने पर भी risk/cash fit न हो तो trade skip होगा.")
    st.error(
        "यह v1.3 अभी Navia API या Live Trading से जुड़ा नहीं है। "
        "स्थायी cloud database अभी configure नहीं है; Streamlit Cloud restart/redeploy "
        "पर स्थानीय state file मिट सकती है। हर सत्र के बाद CSV डाउनलोड करके सुरक्षित रखें."
    )

st.caption("BG AI TRADER v1.3 · India NSE only · Educational paper trading · No profit guarantee")
