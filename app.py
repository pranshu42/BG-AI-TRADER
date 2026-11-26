import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from pathlib import Path

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "bg_ai_trader.db"
START_CAPITAL = 5000.0
RISK_PER_TRADE = 25.0
DAILY_LOSS_LIMIT = 50.0
MAX_NEW_TRADES_PER_DAY = 2

st.set_page_config(page_title="BG AI TRADER v1.5", page_icon="📈", layout="wide")

def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY CHECK(id=1), capital REAL NOT NULL)""")
        con.execute("INSERT OR IGNORE INTO account(id, capital) VALUES(1, ?)", (START_CAPITAL,))
        con.execute("""CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opened_at TEXT NOT NULL, closed_at TEXT,
            market TEXT NOT NULL, instrument TEXT NOT NULL,
            symbol TEXT NOT NULL, option_type TEXT, strike REAL, expiry TEXT,
            lot_size INTEGER NOT NULL, lots INTEGER NOT NULL,
            entry REAL NOT NULL, exit REAL, stop REAL, target REAL,
            status TEXT NOT NULL, pnl REAL DEFAULT 0,
            note TEXT DEFAULT '')""")
        con.execute("""CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT, scanned_at TEXT NOT NULL,
            market TEXT, symbol TEXT, signal TEXT, reason TEXT)""")

def account_capital():
    with db() as con:
        return float(con.execute("SELECT capital FROM account WHERE id=1").fetchone()["capital"])

def trades_df(status=None):
    with db() as con:
        if status:
            rows = con.execute("SELECT * FROM trades WHERE status=? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM trades ORDER BY id DESC").fetchall()
    return pd.DataFrame([dict(r) for r in rows])

def realized_today():
    today = date.today().isoformat()
    df = trades_df("CLOSED")
    if df.empty:
        return 0.0
    df["closed_day"] = pd.to_datetime(df["closed_at"], errors="coerce").dt.date.astype(str)
    return float(df.loc[df.closed_day == today, "pnl"].sum())

def buys_today():
    today = date.today().isoformat()
    df = trades_df()
    if df.empty:
        return 0
    df["opened_day"] = pd.to_datetime(df["opened_at"], errors="coerce").dt.date.astype(str)
    return int((df.opened_day == today).sum())

def open_pnl():
    df = trades_df("OPEN")
    if df.empty:
        return 0.0
    return 0.0  # live marks are not assumed; user can close using entered exit premium

def add_trade(market, instrument, symbol, option_type, strike, expiry,
              lot_size, lots, entry, stop, target, note):
    now = datetime.now().isoformat(timespec="seconds")
    with db() as con:
        con.execute("""INSERT INTO trades
        (opened_at,market,instrument,symbol,option_type,strike,expiry,lot_size,lots,
         entry,stop,target,status,note)
         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
         (now,market,instrument,symbol,option_type,strike,expiry,lot_size,lots,
          entry,stop,target,"OPEN",note))

def close_trade(trade_id, exit_price):
    with db() as con:
        row = con.execute("SELECT * FROM trades WHERE id=? AND status='OPEN'", (trade_id,)).fetchone()
        if not row:
            return False, "यह खुला Paper Trade नहीं मिला।"
        pnl = (float(exit_price) - float(row["entry"])) * int(row["lot_size"]) * int(row["lots"])
        con.execute("""UPDATE trades SET exit=?, pnl=?, status='CLOSED', closed_at=?
                       WHERE id=?""",
                    (float(exit_price), pnl, datetime.now().isoformat(timespec="seconds"), trade_id))
        return True, pnl

def record_scan(rows):
    with db() as con:
        for r in rows:
            con.execute("INSERT INTO scans(scanned_at,market,symbol,signal,reason) VALUES(?,?,?,?,?)",
                        (datetime.now().isoformat(timespec="seconds"), r[0], r[1], r[2], r[3]))

init_db()
st.title("📈 BG AI TRADER v1.5")
st.caption("India NSE · Intraday + Options · Paper Trading only")

st.warning(
    "यह केवल शैक्षिक Paper Trading सिम्युलेटर है। कोई वास्तविक ऑर्डर नहीं भेजा जाता। "
    "Options के लाइव प्रीमियम/ऑप्शन-चेन की पुष्टि इस संस्करण में नहीं होती। "
    "Premium आप स्वयं भरेंगे; ऐप उसे लाइव डेटा नहीं मानेगा।"
)

tabs = st.tabs(["🏠 Dashboard", "📊 NSE Intraday", "🧩 Options Paper Trading",
                "📦 Open Positions", "📜 Trade History", "⚙️ Risk Settings"])

with tabs[0]:
    cap = account_capital()
    history = trades_df()
    closed = history[history.status == "CLOSED"] if not history.empty else pd.DataFrame()
    total_pnl = float(closed.pnl.sum()) if not closed.empty else 0.0
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Virtual Capital", f"₹{cap:,.2f}")
    c2.metric("Available Cash*", f"₹{cap:,.2f}")
    c3.metric("Total Realized Paper P&L", f"₹{total_pnl:,.2f}")
    c4.metric("Open Positions", len(trades_df("OPEN")))
    st.caption("*इस शुरुआती संस्करण में cash reservation/margin calculation शामिल नहीं है।")
    st.info(f"आज का realized P&L: ₹{realized_today():.2f} · आज के नए trades: {buys_today()}/{MAX_NEW_TRADES_PER_DAY}")
    st.markdown("**रणनीति का सिद्धांत:** अच्छा अवसर न मिले तो WAIT। हर दिन ट्रेड करना जरूरी नहीं।")

with tabs[1]:
    st.subheader("NSE Intraday Paper Journal")
    st.write("इस पेज पर आप अपने verified NSE signal और market price के आधार पर paper trade दर्ज कर सकते हैं।")
    st.info("यहाँ कोई automatic market scanner या live feed नहीं है। गलत/पुराने डेटा से बचने के लिए price आप स्वयं सत्यापित करें।")
    with st.form("intraday_form"):
        symbol = st.selectbox("NSE Symbol", ["RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY",
            "SBIN","ITC","BHARTIARTL","LT","AXISBANK","KOTAKBANK","MARUTI","SUNPHARMA","TATAMOTORS"])
        side = st.radio("Paper Side", ["BUY"])
        entry = st.number_input("Verified entry price (₹)", min_value=0.05, value=100.0, step=0.05)
        stop = st.number_input("Stop-loss price (₹)", min_value=0.01, value=98.0, step=0.05)
        target = st.number_input("Target price (₹)", min_value=0.01, value=104.0, step=0.05)
        qty = st.number_input("Quantity (shares)", min_value=1, max_value=100000, value=1)
        note = st.text_input("Reason / setup")
        submitted = st.form_submit_button("Record Intraday Paper BUY")
    if submitted:
        risk = (entry-stop)*qty
        if stop >= entry or target <= entry:
            st.error("BUY के लिए Stop Loss entry से नीचे और Target entry से ऊपर होना चाहिए।")
        elif risk > RISK_PER_TRADE:
            st.error(f"Trade skip: अनुमानित जोखिम ₹{risk:.2f}, सीमा ₹{RISK_PER_TRADE:.2f} है।")
        elif realized_today() <= -DAILY_LOSS_LIMIT:
            st.error("आज की daily loss limit पूरी हो चुकी है।")
        elif buys_today() >= MAX_NEW_TRADES_PER_DAY:
            st.error("आज के अधिकतम नए trades पूरे हो चुके हैं।")
        else:
            add_trade("NSE","INTRADAY",symbol,None,None,None,1,int(qty),entry,stop,target,note)
            st.success(f"Paper BUY दर्ज: {qty} {symbol} @ ₹{entry:.2f}")
    st.caption("इस पेज पर stop/target अपने आप market में monitor नहीं होते। Exit premium/price आप Open Positions में दर्ज करेंगे।")

with tabs[2]:
    st.subheader("Options Paper Trading")
    st.write("NIFTY, BANKNIFTY और चुने हुए NSE stock options के लिए CE/PE paper journal.")
    st.warning("Options contract specifications (expiry, strike, lot size और premium) exchange/broker से जांचकर भरें। गलत lot size से P&L गलत होगा।")
    underlyings = ["NIFTY","BANKNIFTY","RELIANCE","HDFCBANK","ICICIBANK","INFY","SBIN",
                   "TCS","TATAMOTORS","AXISBANK","KOTAKBANK","LT","BHARTIARTL","ITC",
                   "MARUTI","SUNPHARMA"]
    with st.form("options_form"):
        underlying = st.selectbox("Underlying", underlyings)
        opt_type = st.radio("Option Type", ["CE","PE"], horizontal=True)
        strike = st.number_input("Strike Price", min_value=0.0, value=25000.0, step=50.0)
        expiry = st.date_input("Expiry Date", value=date.today())
        lot_size = st.number_input("Exchange-verified lot size", min_value=1, max_value=10000, value=1)
        lots = st.number_input("Number of lots", min_value=1, max_value=100, value=1)
        premium = st.number_input("Verified option premium (₹)", min_value=0.05, value=100.0, step=0.05)
        sl = st.number_input("Stop-loss premium (₹)", min_value=0.01, value=80.0, step=0.05)
        tgt = st.number_input("Target premium (₹)", min_value=0.01, value=140.0, step=0.05)
        comment = st.text_input("Signal / reason (optional)")
        opt_submit = st.form_submit_button("Record Options Paper BUY")
    if opt_submit:
        risk = (premium-sl)*lot_size*lots
        cost = premium*lot_size*lots
        if sl >= premium or tgt <= premium:
            st.error("Options BUY के लिए SL premium से नीचे और Target premium से ऊपर होना चाहिए।")
        elif risk > RISK_PER_TRADE:
            st.error(f"Trade skip: कुल अनुमानित जोखिम ₹{risk:.2f}, सीमा ₹{RISK_PER_TRADE:.2f} है।")
        elif cost > account_capital():
            st.error(f"Trade skip: अनुमानित premium cost ₹{cost:.2f}, virtual capital ₹{account_capital():.2f} से अधिक है।")
        elif realized_today() <= -DAILY_LOSS_LIMIT:
            st.error("आज की daily loss limit पूरी हो चुकी है।")
        elif buys_today() >= MAX_NEW_TRADES_PER_DAY:
            st.error("आज के अधिकतम नए trades पूरे हो चुके हैं।")
        else:
            contract = f"{underlying} {strike:g} {opt_type}"
            add_trade("NSE","OPTIONS",contract,opt_type,strike,expiry.isoformat(),
                      int(lot_size),int(lots),premium,sl,tgt,comment)
            st.success(f"Paper BUY दर्ज: {contract}, expiry {expiry}, premium ₹{premium:.2f}")
    st.markdown("**Options BUY P&L:** (Exit Premium − Entry Premium) × Lot Size × Lots. Brokerage, taxes, slippage और exercise/expiry settlement शामिल नहीं हैं.")

with tabs[3]:
    st.subheader("Open Paper Positions")
    open_df = trades_df("OPEN")
    if open_df.empty:
        st.info("अभी कोई खुली Paper Position नहीं है।")
    else:
        view_cols = ["id","opened_at","instrument","symbol","option_type","strike","expiry",
                     "lots","lot_size","entry","stop","target"]
        st.dataframe(open_df[view_cols], use_container_width=True, hide_index=True)
        st.markdown("#### Close a Paper Position")
        ids = open_df.id.astype(int).tolist()
        selected = st.selectbox("Trade ID", ids)
        chosen = open_df[open_df.id == selected].iloc[0]
        exit_price = st.number_input("Verified exit price / option premium (₹)",
                                     min_value=0.01, value=float(chosen.entry), step=0.05, key="exit_price")
        if st.button("Close Paper Trade"):
            ok, result = close_trade(int(selected), float(exit_price))
            if ok:
                st.success(f"Trade closed. Realized Paper P&L: ₹{result:.2f}")
                st.rerun()
            else:
                st.error(result)

with tabs[4]:
    st.subheader("Trade History")
    hist = trades_df()
    if hist.empty:
        st.info("अभी कोई trade history नहीं है।")
    else:
        st.dataframe(hist, use_container_width=True, hide_index=True)
        csv = hist.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Trade History CSV", csv,
                           file_name=f"bg_ai_trader_history_{date.today()}.csv",
                           mime="text/csv")

with tabs[5]:
    st.subheader("Risk Settings")
    st.write(f"- Virtual capital: ₹{START_CAPITAL:,.0f}")
    st.write(f"- Planned risk cap: ₹{RISK_PER_TRADE:,.0f} per trade")
    st.write(f"- Daily realized loss limit: ₹{DAILY_LOSS_LIMIT:,.0f}")
    st.write(f"- Maximum new trades/day: {MAX_NEW_TRADES_PER_DAY}")
    st.write("- Strategy preference: WAIT when setup is unclear.")
    st.error("यह prototype investment advice नहीं है। यह profit की गारंटी नहीं देता। Options में पूरा premium loss हो सकता है।")

st.divider()
st.caption("BG AI TRADER v1.5 · India NSE · Intraday + Options Paper Trading · No live orders · No profit guarantee")
