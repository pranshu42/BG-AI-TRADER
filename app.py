import streamlit as st
import pandas as pd
from datetime import datetime, date

st.set_page_config(page_title="BG AI TRADER", page_icon="📈", layout="wide")

START_CAPITAL = 5000.0
RISK_PER_TRADE = 25.0
DAILY_LOSS_LIMIT = 50.0
MAX_TRADES_PER_DAY = 2

if "cash" not in st.session_state:
    st.session_state.cash = START_CAPITAL
    st.session_state.positions = {}
    st.session_state.trades = []
    st.session_state.realized_today = 0.0
    st.session_state.trade_day = date.today().isoformat()
    st.session_state.live_enabled = False

# Reset the daily counters when the calendar date changes.
today = date.today().isoformat()
if st.session_state.trade_day != today:
    st.session_state.trade_day = today
    st.session_state.realized_today = 0.0

st.title("📈 BG AI TRADER")
st.caption("Version 1.0 · Cloud Paper Trading · Navia Live API अभी कनेक्ट नहीं है")

st.warning(
    "यह केवल Paper Trading अभ्यास है। कीमतें आप स्वयं भरेंगे; यह लाइव मार्केट डेटा या निवेश सलाह नहीं है। "
    "कोई वास्तविक ऑर्डर नहीं भेजा जाता। ऐप रीस्टार्ट होने पर इस शुरुआती संस्करण का डेटा मिट सकता है।"
)

# Header metrics
positions = st.session_state.positions
open_value = sum(p["qty"] * p["ltp"] for p in positions.values())
unrealized = sum((p["ltp"] - p["avg"]) * p["qty"] for p in positions.values())
equity = st.session_state.cash + open_value
total_pnl = (equity - START_CAPITAL)

m1, m2, m3, m4 = st.columns(4)
m1.metric("शुरुआती वर्चुअल पूंजी", f"₹{START_CAPITAL:,.2f}")
m2.metric("उपलब्ध वर्चुअल कैश", f"₹{st.session_state.cash:,.2f}")
m3.metric("Open P&L", f"₹{unrealized:,.2f}")
m4.metric("कुल वर्चुअल P&L", f"₹{total_pnl:,.2f}")

st.divider()
tab_trade, tab_positions, tab_history, tab_rules = st.tabs(
    ["🧾 Paper Order", "📦 Positions", "📜 Trade History", "🛡️ Risk Rules"]
)

with tab_trade:
    st.subheader("Paper Order Ticket")
    left, right = st.columns([1, 1])
    with left:
        symbol = st.text_input("Stock Symbol", value="RELIANCE").strip().upper()
        exchange = st.selectbox("Exchange", ["NSE", "BSE", "NASDAQ", "NYSE"])
        side = st.radio("Action", ["BUY", "SELL"], horizontal=True)
        qty = st.number_input("Quantity", min_value=1, max_value=100000, value=1, step=1)
    with right:
        entry = st.number_input("Simulated execution price (₹ / local currency)", min_value=0.01, value=100.0, step=0.05)
        if side == "BUY":
            stop = st.number_input("Stop Loss price", min_value=0.01, value=max(0.05, round(entry - 2.0, 2)), step=0.05)
            target = st.number_input("Target price", min_value=0.01, value=round(entry + 4.0, 2), step=0.05)
            risk = max(0.0, (entry - stop) * qty)
            st.metric("Estimated risk on this trade", f"{risk:,.2f}")
            st.caption(f"Risk cap: {RISK_PER_TRADE:.0f} per trade (currency units).")
        else:
            stop = target = None
            risk = 0.0
            held = positions.get(f"{exchange}:{symbol}", {}).get("qty", 0)
            st.info(f"Currently held in this paper account: {held} shares")

    if st.button("Place Paper Order", type="primary", use_container_width=True):
        key = f"{exchange}:{symbol}"
        if not symbol:
            st.error("कृपया Stock Symbol भरें।")
        elif st.session_state.realized_today <= -DAILY_LOSS_LIMIT:
            st.error("Daily loss limit hit. आज के लिए नए orders बंद हैं।")
        elif len([t for t in st.session_state.trades if t["date"] == today]) >= MAX_TRADES_PER_DAY:
            st.error(f"आज की अधिकतम {MAX_TRADES_PER_DAY} paper trades की सीमा पूरी हो गई है।")
        elif side == "BUY":
            if stop >= entry:
                st.error("BUY के लिए Stop Loss, entry price से नीचे होना चाहिए।")
            elif target <= entry:
                st.error("BUY के लिए Target, entry price से ऊपर होना चाहिए।")
            elif risk > RISK_PER_TRADE:
                st.error(f"इस order का अनुमानित जोखिम {risk:.2f} है, जो {RISK_PER_TRADE:.2f} की सीमा से अधिक है। Quantity घटाएँ या Stop Loss पास रखें।")
            elif entry * qty > st.session_state.cash:
                st.error("पर्याप्त virtual cash नहीं है।")
            else:
                old = positions.get(key, {"qty": 0, "avg": 0.0, "ltp": entry, "stop": stop, "target": target})
                new_qty = old["qty"] + int(qty)
                new_avg = ((old["qty"] * old["avg"]) + (qty * entry)) / new_qty
                positions[key] = {"qty": new_qty, "avg": new_avg, "ltp": entry, "stop": stop, "target": target}
                st.session_state.cash -= entry * qty
                st.session_state.trades.append({
                    "date": today, "time": datetime.now().strftime("%H:%M:%S"),
                    "symbol": key, "side": "BUY", "qty": int(qty), "price": float(entry),
                    "pnl": 0.0, "note": "Paper execution"
                })
                st.success(f"Paper BUY दर्ज हुआ: {qty} {symbol} @ {entry:.2f}")
        else:
            pos = positions.get(key)
            if not pos or pos["qty"] < qty:
                st.error("Sell quantity आपकी उपलब्ध paper holding से अधिक है।")
            else:
                pnl = (entry - pos["avg"]) * qty
                st.session_state.cash += entry * qty
                st.session_state.realized_today += pnl
                remaining = pos["qty"] - int(qty)
                if remaining == 0:
                    del positions[key]
                else:
                    pos["qty"] = remaining
                    pos["ltp"] = entry
                st.session_state.trades.append({
                    "date": today, "time": datetime.now().strftime("%H:%M:%S"),
                    "symbol": key, "side": "SELL", "qty": int(qty), "price": float(entry),
                    "pnl": float(pnl), "note": "Paper execution"
                })
                st.success(f"Paper SELL दर्ज हुआ: {qty} {symbol} @ {entry:.2f} · Realized P&L: {pnl:.2f}")

    st.caption("ध्यान दें: इस शुरुआती संस्करण में BUY/SELL बटन केवल वर्चुअल लेजर अपडेट करते हैं। Stop Loss/Target अभी ऑटो-ट्रिगर नहीं होते।")

with tab_positions:
    st.subheader("Open Paper Positions")
    if positions:
        rows = []
        for key, p in positions.items():
            rows.append({
                "Symbol": key, "Qty": p["qty"], "Average Buy": p["avg"],
                "Latest Simulated Price": p["ltp"], "Unrealized P&L": (p["ltp"] - p["avg"]) * p["qty"],
                "Stop Loss": p["stop"], "Target": p["target"]
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("**Update simulated prices**")
        for key, p in list(positions.items()):
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(key)
            new_ltp = c2.number_input(f"Price for {key}", min_value=0.01, value=float(p["ltp"]), key=f"ltp_{key}")
            if c3.button("Update", key=f"upd_{key}"):
                positions[key]["ltp"] = float(new_ltp)
                st.rerun()
    else:
        st.info("अभी कोई open paper position नहीं है। Paper Order टैब से एक अभ्यास order दर्ज करें।")

with tab_history:
    st.subheader("Paper Trade History")
    if st.session_state.trades:
        df = pd.DataFrame(st.session_state.trades)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download trade history CSV", df.to_csv(index=False).encode("utf-8"), "bg_ai_trader_paper_history.csv", "text/csv")
    else:
        st.info("अभी कोई paper trade दर्ज नहीं है।")

with tab_rules:
    st.subheader("Risk Controls — शुरुआती अभ्यास सेटिंग")
    st.write(f"- Starting virtual capital: ₹{START_CAPITAL:,.0f}")
    st.write(f"- Maximum planned risk per BUY: ₹{RISK_PER_TRADE:,.0f}")
    st.write(f"- Daily realized loss stop: ₹{DAILY_LOSS_LIMIT:,.0f}")
    st.write(f"- Maximum paper orders per day: {MAX_TRADES_PER_DAY}")
    st.write("- F&O और leverage इस संस्करण में शामिल नहीं हैं।")
    st.write("- कोई live Navia API key या secret इस ऐप में नहीं डाला गया है।")
    st.write("- Stop Loss और Target अभी केवल रिकॉर्ड होते हैं; स्वचालित execution लागू नहीं है।")
    st.error("Live Trading अभी बंद है। इस ऐप को वास्तविक पैसे के ऑर्डर भेजने के लिए इस्तेमाल न करें।")

st.divider()
st.caption("BG AI TRADER · Educational paper-trading prototype · No profit guarantee")
