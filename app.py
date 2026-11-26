import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import json

st.set_page_config(page_title="BG AI TRADER", page_icon="📈", layout="wide")

# BG AI TRADER v1.4 — India NSE intraday PAPER trading only.
IST = ZoneInfo("Asia/Kolkata")
START_CAPITAL = 5000.0
RISK_PER_TRADE = 25.0
DAILY_LOSS_LIMIT = 50.0
MAX_NEW_BUYS_PER_DAY = 2
STOP_LOSS_PCT = 0.005       # 0.5%
TARGET_PCT = 0.010          # 1.0%
EXIT_TIME = time(15, 15)    # close paper positions before NSE cash-market close
INTERVAL = "5m"
WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "SBIN.NS", "ITC.NS", "BHARTIARTL.NS",
    "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "MARUTI.NS"
]
STATE_FILE = "bg_ai_trader_intraday_state.json"


def now_ist():
    return datetime.now(IST)


def today_ist():
    return now_ist().date().isoformat()


def fresh_state():
    return {
        "cash": START_CAPITAL,
        "positions": {},
        "trades": [],
        "realized_today": 0.0,
        "trade_day": today_ist(),
        "last_scan": "अभी स्कैन नहीं हुआ",
        "scan_rows": []
    }


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        state = fresh_state()
        state.update(saved)
        return state
    except Exception:
        return fresh_state()


def save_state():
    state = {
        "cash": st.session_state.cash,
        "positions": st.session_state.positions,
        "trades": st.session_state.trades,
        "realized_today": st.session_state.realized_today,
        "trade_day": st.session_state.trade_day,
        "last_scan": st.session_state.last_scan,
        "scan_rows": st.session_state.scan_rows
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


if "initialized" not in st.session_state:
    saved = load_state()
    for key, value in saved.items():
        st.session_state[key] = value
    st.session_state.initialized = True

# Reset the daily loss counter and daily BUY count by using trade dates in history.
today = today_ist()
if st.session_state.trade_day != today:
    # Intraday positions must not silently carry into another trading day.
    # If the app was not scanned at the prior close, close them at the last
    # simulated price available in the saved paper ledger and label that clearly.
    previous_day = st.session_state.trade_day
    for symbol, pos in list(st.session_state.positions.items()):
        qty = int(pos["qty"])
        exit_price = float(pos.get("ltp", pos["avg"]))
        pnl = (exit_price - float(pos["avg"])) * qty
        st.session_state.cash += exit_price * qty
        st.session_state.trades.append({
            "Date": previous_day,
            "Time": "15:15:00 (estimated stale-price square-off)",
            "Symbol": symbol.replace(".NS", ""),
            "Side": "SELL",
            "Qty": qty,
            "Price ₹": round(exit_price, 2),
            "Realized P&L ₹": round(pnl, 2),
            "Note": "Previous-day forced paper square-off at last saved simulated price; not a live quote"
        })
        del st.session_state.positions[symbol]
    st.session_state.trade_day = today
    st.session_state.realized_today = 0.0
    save_state()


def as_series(value):
    if isinstance(value, pd.DataFrame):
        return value.iloc[:, 0]
    return value


def rsi_series(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def get_intraday_signal(symbol):
    # Yahoo Finance intraday data is for practice only; it can be delayed or incomplete.
    data = yf.download(
        symbol, period="5d", interval=INTERVAL,
        auto_adjust=True, progress=False, threads=False
    )
    if data is None or data.empty or len(data) < 30:
        return None, "5-minute data unavailable / insufficient"

    close = as_series(data["Close"]).dropna()
    high = as_series(data["High"]).reindex(close.index)
    low = as_series(data["Low"]).reindex(close.index)
    volume = as_series(data["Volume"]).reindex(close.index).fillna(0)
    if len(close) < 30:
        return None, "Insufficient 5-minute candles"

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    rsi = rsi_series(close)
    vol_avg = volume.rolling(20).mean()

    # Intraday VWAP is reset for the current trading date.
    idx = close.index
    try:
        local_dates = idx.tz_convert("Asia/Kolkata").date
    except Exception:
        local_dates = idx.date
    current_date = now_ist().date()
    today_mask = [d == current_date for d in local_dates]
    today_close = close.loc[today_mask]
    today_high = high.loc[today_mask]
    today_low = low.loc[today_mask]
    today_volume = volume.loc[today_mask]
    if len(today_close) < 3:
        return None, "आज के पर्याप्त intraday candles उपलब्ध नहीं"

    typical = (today_high + today_low + today_close) / 3
    cumulative_volume = today_volume.cumsum()
    vwap_series = (typical * today_volume).cumsum() / cumulative_volume.replace(0, 1e-9)
    vwap = float(vwap_series.iloc[-1])

    price = float(close.iloc[-1])
    current_rsi = float(rsi.iloc[-1])
    current_volume = float(volume.iloc[-1])
    average_volume = float(vol_avg.iloc[-1]) if pd.notna(vol_avg.iloc[-1]) else 0.0
    e9 = float(ema9.iloc[-1])
    e21 = float(ema21.iloc[-1])

    if not all(pd.notna(x) for x in [price, current_rsi, e9, e21, vwap]):
        return None, "Indicator data incomplete"

    volume_ok = average_volume > 0 and current_volume >= average_volume
    buy = e9 > e21 and 50 <= current_rsi <= 68 and price > vwap and volume_ok
    sell_trend = e9 < e21

    return {
        "price": price,
        "rsi": current_rsi,
        "ema9": e9,
        "ema21": e21,
        "vwap": vwap,
        "volume_ok": volume_ok,
        "signal": "BUY" if buy else "WAIT",
        "sell_trend": sell_trend
    }, "5m EMA 9/21 + RSI(14) + VWAP + volume"


def add_trade(symbol, side, qty, price, pnl=0.0, note=""):
    st.session_state.trades.append({
        "Date": today_ist(),
        "Time": now_ist().strftime("%H:%M:%S"),
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
    rows = []
    prices = {}
    sell_trends = {}

    for symbol in WATCHLIST:
        try:
            result, reason = get_intraday_signal(symbol)
            if result is None:
                rows.append({
                    "Market": "India NSE", "Symbol": symbol.replace(".NS", ""),
                    "Price ₹": None, "RSI": None, "VWAP ₹": None,
                    "Signal": "NO DATA", "Reason": reason
                })
            else:
                prices[symbol] = result["price"]
                sell_trends[symbol] = result["sell_trend"]
                rows.append({
                    "Market": "India NSE",
                    "Symbol": symbol.replace(".NS", ""),
                    "Price ₹": round(result["price"], 2),
                    "RSI": round(result["rsi"], 1),
                    "VWAP ₹": round(result["vwap"], 2),
                    "Signal": result["signal"],
                    "Reason": reason
                })
        except Exception as exc:
            rows.append({
                "Market": "India NSE", "Symbol": symbol.replace(".NS", ""),
                "Price ₹": None, "RSI": None, "VWAP ₹": None,
                "Signal": "ERROR", "Reason": str(exc)[:100]
            })

    current_time = now_ist().time()
    force_square_off = current_time >= EXIT_TIME

    # Evaluate exits for existing paper positions.
    for symbol in list(st.session_state.positions.keys()):
        if symbol not in prices:
            continue
        pos = st.session_state.positions[symbol]
        ltp = float(prices[symbol])
        pos["ltp"] = ltp

        if ltp <= float(pos["stop"]):
            close_position(symbol, ltp, "Intraday Paper Stop Loss")
        elif ltp >= float(pos["target"]):
            close_position(symbol, ltp, "Intraday Paper Target")
        elif sell_trends.get(symbol, False):
            close_position(symbol, ltp, "5m EMA bearish exit")
        elif force_square_off:
            close_position(symbol, ltp, "Intraday square-off scan")

    buys_today = sum(
        1 for trade in st.session_state.trades
        if trade["Date"] == today and trade["Side"] == "BUY"
    )
    new_buys = 0
    remaining_slots = max(0, MAX_NEW_BUYS_PER_DAY - buys_today)

    market_open = time(9, 15) <= current_time < EXIT_TIME
    loss_limit_hit = st.session_state.realized_today <= -DAILY_LOSS_LIMIT

    if market_open and not loss_limit_hit:
        for row in rows:
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
            qty_by_risk = int(RISK_PER_TRADE // risk_per_share) if risk_per_share > 0 else 0
            qty_by_cash = int(st.session_state.cash // entry) if entry > 0 else 0
            qty = min(qty_by_risk, qty_by_cash)

            if qty < 1:
                row["Signal"] = "WAIT"
                row["Reason"] = "₹25 risk budget / available cash में 1 शेयर फिट नहीं; skip"
                continue

            planned_risk = risk_per_share * qty
            if planned_risk > RISK_PER_TRADE + 0.01:
                row["Signal"] = "WAIT"
                row["Reason"] = "Risk cap से अधिक; trade skip"
                continue

            st.session_state.cash -= qty * entry
            st.session_state.positions[symbol] = {
                "qty": qty, "avg": entry, "ltp": entry,
                "stop": stop, "target": target,
                "planned_risk": round(planned_risk, 2),
                "entry_date": today
            }
            add_trade(symbol, "BUY", qty, entry, 0.0, "Auto Intraday Paper BUY")
            new_buys += 1
            remaining_slots -= 1

    st.session_state.scan_rows = rows
    st.session_state.last_scan = now_ist().strftime("%d-%m-%Y %H:%M:%S IST")
    save_state()
    return new_buys


st.title("📈 BG AI TRADER")
st.caption("Version 1.4 · India NSE Intraday · Auto Paper BUY/SELL · Live broker API OFF")
st.warning(
    "यह केवल ₹5,000 virtual cash वाला educational paper-trading अभ्यास है। "
    "कोई वास्तविक ऑर्डर या असली पैसा इस्तेमाल नहीं होता। Yahoo Finance का 5-minute data "
    "विलंबित/अधूरा हो सकता है। BUY/SELL और Stop/Target जाँच केवल Scan बटन दबाने पर होती है; "
    "यह 24/7 background bot नहीं है।"
)

now = now_ist()
if time(9, 15) <= now.time() < time(15, 30):
    st.info(f"भारतीय बाजार समय: {now.strftime('%H:%M:%S')} IST · Market session")
else:
    st.info(f"भारतीय समय: {now.strftime('%d-%m-%Y %H:%M:%S')} IST · NSE regular session 09:15–15:30")

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
    f"Last scan: {st.session_state.last_scan} · Risk/trade ₹{RISK_PER_TRADE:.0f} "
    f"· Daily realized loss limit ₹{DAILY_LOSS_LIMIT:.0f} · "
    f"Max new BUY/day {MAX_NEW_BUYS_PER_DAY} · Stop {STOP_LOSS_PCT*100:.1f}% "
    f"· Target {TARGET_PCT*100:.1f}%"
)

scanner_tab, positions_tab, history_tab, rules_tab = st.tabs([
    "🤖 NSE Intraday Scanner", "📦 Open Positions", "📜 Trade History", "🛡️ Rules"
])

with scanner_tab:
    st.write(
        "BUY नियम (5-minute candles): EMA9 > EMA21, RSI 50–68, "
        "Price > intraday VWAP और volume confirmation."
    )
    st.write(
        "SELL नियम: Stop Loss 0.5%, Target 1%, 5-minute EMA bearish signal, "
        "या 15:15 IST के बाद अगली scan पर square-off."
    )
    st.warning(
        "अच्छा signal न मिलने पर WAIT रहेगा। एक शेयर की quantity तभी खरीदी जाएगी "
        "जब planned stop-loss risk ₹25 और उपलब्ध virtual cash दोनों में फिट हों।"
    )
    if st.button("🔎 Scan NSE + Execute Intraday Paper Trades", type="primary", use_container_width=True):
        with st.spinner("NSE के 5-minute candles जाँचे जा रहे हैं..."):
            count = scan_and_trade()
        st.success(f"स्कैन पूरा। नए Paper BUY: {count}")
        if st.session_state.realized_today <= -DAILY_LOSS_LIMIT:
            st.error("आज की ₹50 realized loss limit पूरी हो गई है। नए BUY बंद हैं।")
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
        st.caption("Open positions की exit जाँच अगली manual scan पर होगी। 15:15 के बाद scan करने पर square-off simulation होगा।")
    else:
        st.info("अभी कोई open intraday paper position नहीं है।")

with history_tab:
    if st.session_state.trades:
        history = pd.DataFrame(st.session_state.trades)
        st.dataframe(history, use_container_width=True, hide_index=True)
        st.download_button(
            "Download Trade History CSV",
            history.to_csv(index=False).encode("utf-8"),
            "bg_ai_trader_v1_4_intraday_history.csv",
            "text/csv"
        )
    else:
        st.info("अभी कोई paper trade दर्ज नहीं है।")

with rules_tab:
    st.write("- केवल India NSE cash-equity watchlist; USA, F&O और leverage बंद.")
    st.write("- ₹5,000 virtual starting capital; कोई real order नहीं.")
    st.write("- 5-minute EMA9/EMA21, RSI14, VWAP और volume confirmation.")
    st.write("- प्रति ट्रेड planned stop-loss risk अधिकतम ₹25.")
    st.write("- Daily realized loss limit ₹50; अधिकतम 2 नए BUY प्रतिदिन.")
    st.write("- Stop Loss, Target, bearish EMA exit और 15:15 square-off अगली manual scan पर जाँचे जाते हैं.")
    st.write("- Streamlit app background में scan नहीं करता; app खुला रखकर scan button दबाना होगा.")
    st.error(
        "यह v1.4 Navia API या live trading से जुड़ा नहीं है। Yahoo Finance data exchange का official live feed नहीं है। "
        "Streamlit Cloud restart/redeploy पर local state file मिट सकती है; CSV history नियमित डाउनलोड करें। "
        "Paper results वास्तविक execution, slippage या profit की गारंटी नहीं हैं।"
    )

st.caption("BG AI TRADER v1.4 · India NSE intraday · Educational paper trading only · No profit guarantee")
