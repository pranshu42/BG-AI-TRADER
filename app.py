import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="BG AI TRADER", page_icon="📈", layout="wide")

START_CAPITAL = 5000.0
RISK_PER_TRADE = 25.0
DAILY_LOSS_LIMIT = 50.0
MAX_NEW_TRADES_PER_DAY = 2
WATCHLIST = {
    "India": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
              "SBIN.NS", "ITC.NS", "BHARTIARTL.NS"],
    "USA": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD"]
}

if "cash" not in st.session_state:
    st.session_state.cash = START_CAPITAL
    st.session_state.positions = {}
    st.session_state.trades = []
    st.session_state.realized_today = 0.0
    st.session_state.trade_day = date.today().isoformat()
    st.session_state.auto_paper = False
    st.session_state.last_scan = "अभी स्कैन नहीं हुआ"

today = date.today().isoformat()
if st.session_state.trade_day != today:
    st.session_state.trade_day = today
    st.session_state.realized_today = 0.0

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

def get_signal(symbol):
    # Yahoo Finance data is used for educational paper simulation only.
    df = yf.download(symbol, period="6mo", interval="1d", auto_adjust=True,
                     progress=False, threads=False)
    if df is None or df.empty or len(df) < 60:
        return None, "डेटा उपलब्ध नहीं"
    close = df["Close"]
    volume = df["Volume"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
        volume = volume.iloc[:, 0]
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    rs = rsi(close)
    vol_avg = volume.rolling(20).mean()
    price = float(close.iloc[-1])
    rsi_now = float(rs.iloc[-1])
    vol_ok = float(volume.iloc[-1]) >= float(vol_avg.iloc[-1])
    bullish = float(ema9.iloc[-1]) > float(ema21.iloc[-1])
    bearish = float(ema9.iloc[-1]) < float(ema21.iloc[-1])
    if bullish and 50 <= rsi_now <= 68 and vol_ok:
        return {"price": price, "rsi": rsi_now, "signal": "BUY"}, "EMA9 > EMA21, RSI 50–68, volume confirmation"
    if bearish or rsi_now > 75:
        return {"price": price, "rsi": rsi_now, "signal": "WAIT"}, "Trend/RSI filter does not support a new BUY"
    return {"price": price, "rsi": rsi_now, "signal": "WAIT"}, "सभी BUY शर्तें पूरी नहीं हुईं"

def log_trade(symbol, side, qty, price, pnl=0.0, note=""):
    st.session_state.trades.append({
        "date": date.today().isoformat(),
        "time": datetime.now().strftime("%H:%M:%S"),
        "symbol": symbol, "side": side, "qty": int(qty),
        "price": round(float(price), 2), "pnl": round(float(pnl), 2),
        "note": note
    })

def manage_existing_positions(prices):
    # Exits are simulated at latest downloaded daily close, not broker executions.
    for symbol, pos in list(st.session_state.positions.items()):
        if symbol not in prices:
            continue
        price = prices[symbol]
        pos["ltp"] = price
        exit_reason = None
        if price <= pos["stop"]:
            exit_reason = "Paper stop-loss triggered"
        elif price >= pos["target"]:
            exit_reason = "Paper target triggered"
        if exit_reason:
            qty = pos["qty"]
            pnl = (price - pos["avg"]) * qty
            st.session_state.cash += price * qty
            st.session_state.realized_today += pnl
            log_trade(symbol, "SELL", qty, price, pnl, exit_reason)
            del st.session_state.positions[symbol]

def auto_scan_and_trade():
    results = []
    prices = {}
    for market, symbols in WATCHLIST.items():
        for symbol in symbols:
            try:
                data, reason = get_signal(symbol)
                if data:
                    prices[symbol] = data["price"]
                    results.append({"Market": market, "Symbol": symbol, "Price": round(data["price"], 2),
                                    "RSI": round(data["rsi"], 1), "Signal": data["signal"], "Reason": reason})
                else:
                    results.append({"Market": market, "Symbol": symbol, "Price": None,
                                    "RSI": None, "Signal": "NO DATA", "Reason": reason})
            except Exception as e:
                results.append({"Market": market, "Symbol": symbol, "Price": None,
                                "RSI": None, "Signal": "ERROR", "Reason": str(e)[:100]})
    manage_existing_positions(prices)

    new_buys = 0
    if st.session_state.realized_today > -DAILY_LOSS_LIMIT:
        todays_new_buys = sum(1 for t in st.session_state.trades
                              if t["date"] == today and t["side"] == "BUY")
        for row in results:
            if row["Signal"] != "BUY" or new_buys >= MAX_NEW_TRADES_PER_DAY:
                continue
            if todays_new_buys + new_buys >= MAX_NEW_TRADES_PER_DAY:
                break
            symbol = row["Symbol"]
            if symbol in st.session_state.positions:
                continue
            price = float(row["Price"])
            # 2% stop and 4% target: 1:2 reward/risk. Position size limited by ₹25 risk.
            stop = round(price * 0.98, 2)
            target = round(price * 1.04, 2)
            risk_per_share = price - stop
            qty_by_risk = int(RISK_PER_TRADE // risk_per_share) if risk_per_share > 0 else 0
            qty_by_cash = int(st.session_state.cash // price) if price > 0 else 0
            qty = min(qty_by_risk, qty_by_cash)
            if qty < 1:
                continue
            cost = qty * price
            st.session_state.cash -= cost
            st.session_state.positions[symbol] = {
                "qty": qty, "avg": price, "ltp": price, "stop": stop, "target": target
            }
            log_trade(symbol, "BUY", qty, price, 0, "Auto paper BUY: EMA9/EMA21 + RSI + volume")
            new_buys += 1
    st.session_state.last_scan = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    return pd.DataFrame(results), new_buys

st.title("📈 BG AI TRADER")
st.caption("Version 1.1 · Auto Paper Trading · Navia Live API कनेक्ट नहीं है")

st.warning(
    "यह शैक्षिक Paper Trading prototype है। यह Yahoo Finance से दैनिक ऐतिहासिक डेटा पढ़ता है; "
    "डेटा विलंबित/अपूर्ण हो सकता है। यह Live Market feed या निवेश सलाह नहीं है। "
    "कोई वास्तविक ऑर्डर नहीं भेजा जाता। Streamlit session restart पर डेटा मिट सकता है।"
)

positions = st.session_state.positions
open_value = sum(p["qty"] * p["ltp"] for p in positions.values())
unrealized = sum((p["ltp"] - p["avg"]) * p["qty"] for p in positions.values())
equity = st.session_state.cash + open_value
total_pnl = equity - START_CAPITAL

m1, m2, m3, m4 = st.columns(4)
m1.metric("Virtual Capital", f"₹{START_CAPITAL:,.2f}")
m2.metric("Available Cash", f"₹{st.session_state.cash:,.2f}")
m3.metric("Open P&L", f"₹{unrealized:,.2f}")
m4.metric("Total Paper P&L", f"₹{total_pnl:,.2f}")

st.info(f"Last scan: {st.session_state.last_scan} · Daily loss limit: ₹{DAILY_LOSS_LIMIT:.0f} · Max new buys/day: {MAX_NEW_TRADES_PER_DAY}")

tab_auto, tab_manual, tab_positions, tab_history, tab_rules = st.tabs(
    ["🤖 Auto Scanner", "🧾 Manual Paper Order", "📦 Positions", "📜 Trade History", "🛡️ Rules"]
)

with tab_auto:
    st.subheader("Automatic Paper Scanner")
    st.write("यह Swing Trading के लिए daily candles पर EMA 9/21, RSI(14) और volume filter जाँचता है।")
    st.write("BUY तभी जब EMA9 > EMA21, RSI 50–68 और आज का volume 20-day average से अधिक/बराबर हो। अन्यथा WAIT.")
    st.warning("Auto Scan बटन दबाने पर डेटा fetch होगा और शर्तें पूरी होने पर अधिकतम 2 नए Paper BUY हो सकते हैं। यह हर समय background में नहीं चलता।")
    if st.button("🔎 Scan India + USA and Execute Paper Trades", type="primary", use_container_width=True):
        with st.spinner("Market data और signals जाँचे जा रहे हैं..."):
            scan_df, buys = auto_scan_and_trade()
        st.session_state["last_scan_df"] = scan_df
        st.success(f"Scan पूरा। नए Paper BUY: {buys}")
    if "last_scan_df" in st.session_state:
        st.dataframe(st.session_state.last_scan_df, use_container_width=True, hide_index=True)
    st.caption("इस संस्करण में scan user द्वारा बटन दबाने पर चलता है; 24/7 autonomous background trading नहीं।")

with tab_manual:
    st.subheader("Manual Paper Order")
    c1, c2 = st.columns(2)
    with c1:
        symbol = st.text_input("Symbol (उदा. NSE: RELIANCE.NS, USA: AAPL)", "RELIANCE.NS").strip().upper()
        side = st.radio("Action", ["BUY", "SELL"], horizontal=True)
        qty = st.number_input("Quantity", min_value=1, max_value=100000, value=1, step=1)
    with c2:
        price = st.number_input("Simulated price", min_value=0.01, value=100.0, step=0.05)
        if side == "BUY":
            stop = st.number_input("Stop Loss", min_value=0.01, value=98.0, step=0.05)
            target = st.number_input("Target", min_value=0.01, value=104.0, step=0.05)
        else:
            stop, target = None, None
    if st.button("Place Manual Paper Order", use_container_width=True):
        if side == "BUY":
            risk = max(0, (price - stop) * qty)
            if stop >= price or target <= price:
                st.error("BUY के लिए Stop Loss नीचे और Target ऊपर होना चाहिए।")
            elif risk > RISK_PER_TRADE:
                st.error(f"Risk ₹{risk:.2f} है; सीमा ₹{RISK_PER_TRADE:.2f} है।")
            elif price * qty > st.session_state.cash:
                st.error("पर्याप्त virtual cash नहीं है।")
            elif symbol in st.session_state.positions:
                st.error("इस symbol की position पहले से खुली है।")
            else:
                st.session_state.cash -= price * qty
                st.session_state.positions[symbol] = {"qty": int(qty), "avg": float(price), "ltp": float(price),
                                                       "stop": float(stop), "target": float(target)}
                log_trade(symbol, "BUY", qty, price, 0, "Manual paper BUY")
                st.success("Paper BUY दर्ज हुआ।")
        else:
            pos = st.session_state.positions.get(symbol)
            if not pos or pos["qty"] < qty:
                st.error("Sell quantity उपलब्ध holding से अधिक है।")
            else:
                pnl = (price - pos["avg"]) * qty
                st.session_state.cash += price * qty
                st.session_state.realized_today += pnl
                rem = pos["qty"] - int(qty)
                if rem == 0:
                    del st.session_state.positions[symbol]
                else:
                    pos["qty"] = rem
                log_trade(symbol, "SELL", qty, price, pnl, "Manual paper SELL")
                st.success(f"Paper SELL दर्ज हुआ। P&L: ₹{pnl:.2f}")

with tab_positions:
    st.subheader("Open Paper Positions")
    if positions:
        data = [{"Symbol": s, "Qty": p["qty"], "Average Buy": p["avg"], "Latest Simulated Price": p["ltp"],
                 "Unrealized P&L": (p["ltp"]-p["avg"])*p["qty"], "Stop Loss": p["stop"], "Target": p["target"]}
                for s,p in positions.items()]
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("अभी कोई open paper position नहीं है।")

with tab_history:
    st.subheader("Paper Trade History")
    if st.session_state.trades:
        hist = pd.DataFrame(st.session_state.trades)
        st.dataframe(hist, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", hist.to_csv(index=False).encode("utf-8"),
                           "bg_ai_trader_paper_history.csv", "text/csv")
    else:
        st.info("अभी कोई paper trade नहीं है।")

with tab_rules:
    st.subheader("Risk & Strategy Rules")
    st.write(f"- Starting capital: ₹{START_CAPITAL:,.0f}")
    st.write(f"- Planned risk per trade: ₹{RISK_PER_TRADE:,.0f}")
    st.write(f"- Daily realized loss limit: ₹{DAILY_LOSS_LIMIT:,.0f}")
    st.write(f"- Maximum new buys per day: {MAX_NEW_TRADES_PER_DAY}")
    st.write("- No F&O, no leverage.")
    st.write("- Swing signals use daily historical candles, not intraday 5-minute data.")
    st.write("- Auto paper trades occur only when you press the scan button.")
    st.error("Live trading is not implemented. No Navia credentials should be entered here.")
st.caption("BG AI TRADER v1.1 · Educational paper-trading only · No profit guarantee")
