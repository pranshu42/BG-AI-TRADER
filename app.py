import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="BG AI TRADER", page_icon="📈", layout="wide")
CAPITAL, RISK, DAILY_LIMIT, MAX_BUYS = 5000.0, 25.0, 50.0, 2
WATCHLIST = ["RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","SBIN.NS",
             "ITC.NS","BHARTIARTL.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","MARUTI.NS"]

if "cash" not in st.session_state:
    st.session_state.cash = CAPITAL
    st.session_state.positions = {}
    st.session_state.trades = []
    st.session_state.realized_today = 0.0
    st.session_state.trade_day = date.today().isoformat()
    st.session_state.last_scan = "अभी स्कैन नहीं हुआ"
    st.session_state.scan_df = pd.DataFrame()

today = date.today().isoformat()
if st.session_state.trade_day != today:
    st.session_state.trade_day, st.session_state.realized_today = today, 0.0

def calc_rsi(s, n=14):
    d = s.diff()
    gain, loss = d.clip(lower=0).rolling(n).mean(), -d.clip(upper=0).rolling(n).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, 1e-9))

def fetch_signal(symbol):
    df = yf.download(symbol, period="6mo", interval="1d", auto_adjust=True, progress=False, threads=False)
    if df is None or df.empty or len(df) < 60:
        return None, "डेटा उपलब्ध नहीं"
    close, volume = df["Close"], df["Volume"]
    if isinstance(close, pd.DataFrame):
        close, volume = close.iloc[:, 0], volume.iloc[:, 0]
    e9, e21 = close.ewm(span=9, adjust=False).mean(), close.ewm(span=21, adjust=False).mean()
    rsi = calc_rsi(close)
    price, r = float(close.iloc[-1]), float(rsi.iloc[-1])
    vol_ok = float(volume.iloc[-1]) >= float(volume.rolling(20).mean().iloc[-1])
    if float(e9.iloc[-1]) > float(e21.iloc[-1]) and 50 <= r <= 68 and vol_ok:
        return {"price": price, "rsi": r, "signal": "BUY"}, "EMA9>EMA21 + RSI 50–68 + volume"
    return {"price": price, "rsi": r, "signal": "WAIT"}, "BUY की सभी शर्तें पूरी नहीं हुईं"

def log(symbol, side, qty, price, pnl=0, note=""):
    st.session_state.trades.append({"Date": date.today().isoformat(), "Time": datetime.now().strftime("%H:%M:%S"),
        "Symbol": symbol.replace(".NS",""), "Side": side, "Qty": int(qty), "Price ₹": round(float(price),2),
        "Realized P&L ₹": round(float(pnl),2), "Note": note})

def run_scan():
    rows, prices = [], {}
    for sym in WATCHLIST:
        try:
            data, reason = fetch_signal(sym)
            if data:
                prices[sym] = data["price"]
                rows.append({"Market":"India NSE","Symbol":sym.replace(".NS",""),"Price ₹":round(data["price"],2),
                             "RSI":round(data["rsi"],1),"Signal":data["signal"],"Reason":reason})
            else:
                rows.append({"Market":"India NSE","Symbol":sym.replace(".NS",""),"Price ₹":None,
                             "RSI":None,"Signal":"NO DATA","Reason":reason})
        except Exception as e:
            rows.append({"Market":"India NSE","Symbol":sym.replace(".NS",""),"Price ₹":None,
                         "RSI":None,"Signal":"ERROR","Reason":str(e)[:90]})

    # Simulated exits: checked only when another scan is manually started.
    for sym, pos in list(st.session_state.positions.items()):
        if sym not in prices: continue
        px = prices[sym]
        pos["ltp"] = px
        reason = "Paper Stop Loss" if px <= pos["stop"] else ("Paper Target" if px >= pos["target"] else "")
        if reason:
            pnl = (px-pos["avg"])*pos["qty"]
            st.session_state.cash += px*pos["qty"]
            st.session_state.realized_today += pnl
            log(sym,"SELL",pos["qty"],px,pnl,reason)
            del st.session_state.positions[sym]

    buys_today = sum(1 for t in st.session_state.trades if t["Date"] == today and t["Side"] == "BUY")
    new_buys = 0
    if st.session_state.realized_today > -DAILY_LIMIT:
        for row in rows:
            if row["Signal"] != "BUY" or buys_today+new_buys >= MAX_BUYS: continue
            sym = row["Symbol"]+".NS"
            if sym in st.session_state.positions: continue
            px = float(row["Price ₹"])
            stop, target = round(px*.98,2), round(px*1.04,2)
            risk_qty = int(RISK // (px-stop)) if px > stop else 0
            cash_qty = int(st.session_state.cash // px) if px > 0 else 0
            qty = min(risk_qty,cash_qty)
            if qty < 1: continue
            st.session_state.cash -= qty*px
            st.session_state.positions[sym] = {"qty":qty,"avg":px,"ltp":px,"stop":stop,"target":target}
            log(sym,"BUY",qty,px,0,"Auto Paper BUY: EMA/RSI/volume")
            new_buys += 1
    st.session_state.last_scan = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    st.session_state.scan_df = pd.DataFrame(rows)
    return new_buys

st.title("📈 BG AI TRADER")
st.caption("Version 1.2 · India NSE Only · Auto Paper Trading · Navia Live API कनेक्ट नहीं है")
st.warning("केवल शैक्षिक Paper Trading। Yahoo Finance का दैनिक ऐतिहासिक डेटा विलंबित/अपूर्ण हो सकता है; यह Live feed या निवेश सलाह नहीं है। कोई वास्तविक ऑर्डर नहीं भेजा जाता। Streamlit session restart पर डेटा मिट सकता है।")

positions = st.session_state.positions
open_value = sum(p["qty"]*p["ltp"] for p in positions.values())
unreal = sum((p["ltp"]-p["avg"])*p["qty"] for p in positions.values())
m = st.columns(4)
m[0].metric("Virtual Capital",f"₹{CAPITAL:,.2f}")
m[1].metric("Available Cash",f"₹{st.session_state.cash:,.2f}")
m[2].metric("Open P&L",f"₹{unreal:,.2f}")
m[3].metric("Total Paper P&L",f"₹{st.session_state.cash+open_value-CAPITAL:,.2f}")
st.info(f"Last scan: {st.session_state.last_scan} · Risk/trade ₹{RISK} · Daily loss limit ₹{DAILY_LIMIT} · Max new buys/day {MAX_BUYS}")

scan_tab, pos_tab, hist_tab, rules_tab = st.tabs(["🤖 NSE Auto Scanner","📦 Positions","📜 Trade History","🛡️ Rules"])
with scan_tab:
    st.write("Swing setup: Daily EMA 9/21, RSI(14), volume confirmation.")
    st.write("BUY तभी: EMA9 > EMA21, RSI 50–68 और volume 20-day average के बराबर/ऊपर। बाकी में WAIT.")
    st.warning("स्कैन और Paper BUY/SELL simulation केवल बटन दबाने पर चलते हैं; यह 24/7 background में नहीं चलता।")
    if st.button("🔎 Scan NSE + Execute Paper Trades",type="primary",use_container_width=True):
        with st.spinner("NSE शेयरों का डेटा जाँचा जा रहा है..."):
            n = run_scan()
        st.success(f"स्कैन पूरा। नए Paper BUY: {n}")
    if not st.session_state.scan_df.empty:
        st.dataframe(st.session_state.scan_df,use_container_width=True,hide_index=True)

with pos_tab:
    if positions:
        st.dataframe(pd.DataFrame([{"Symbol":s.replace(".NS",""),"Qty":p["qty"],"Average Buy ₹":p["avg"],
            "Latest Simulated Price ₹":p["ltp"],"Unrealized P&L ₹":(p["ltp"]-p["avg"])*p["qty"],
            "Stop Loss ₹":p["stop"],"Target ₹":p["target"]} for s,p in positions.items()]),
            use_container_width=True,hide_index=True)
    else: st.info("अभी कोई open paper position नहीं है।")

with hist_tab:
    if st.session_state.trades:
        h = pd.DataFrame(st.session_state.trades)
        st.dataframe(h,use_container_width=True,hide_index=True)
        st.download_button("Download CSV",h.to_csv(index=False).encode("utf-8"),"bg_ai_trader_nse_history.csv","text/csv")
    else: st.info("अभी कोई paper trade नहीं है।")

with rules_tab:
    st.write("- ₹5,000 virtual capital, INR-only accounting")
    st.write("- अधिकतम planned risk ₹25 प्रति trade; daily realized loss limit ₹50")
    st.write("- अधिकतम 2 नए Paper BUY प्रतिदिन")
    st.write("- केवल NSE cash-equity; USA, F&O और leverage बंद")
    st.write("- Stop Loss/Target अगली manual scan पर daily close से जाँचे जाते हैं")
    st.error("Navia API/Live Trading लागू नहीं है। इस ऐप में API key या password न डालें।")

st.caption("BG AI TRADER v1.2 · India NSE only · Educational paper trading · No profit guarantee")
