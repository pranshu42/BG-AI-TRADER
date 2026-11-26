import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timezone, date

st.set_page_config(page_title="BG AI CRYPTO TRADER", page_icon="₿", layout="wide")
st.title("₿ BG AI CRYPTO TRADER v1.4")
st.caption("BTC Paper Trading • Buy the Dip + Short Simulation • ₹5 target per trade")
st.warning("केवल Paper Trading। कोई असली ऑर्डर, Futures या Leverage नहीं। ₹5 लक्ष्य गारंटी नहीं है। Auto Scan लगभग हर 1 मिनट में चलता है और पेज खुला/सक्रिय रहना चाहिए।")

START_CASH, MAX_STAKE, RISK, DAILY_LIMIT, TARGET, STOP = 5000.0, 2500.0, 25.0, 50.0, 5.0, 25.0

@st.cache_data(ttl=20)
def market_data():
    h={"User-Agent":"BG-AI-CRYPTO-TRADER/1.4"}
    now=int(time.time())
    t=requests.get("https://api.exchange.coinbase.com/products/BTC-USD/ticker",headers=h,timeout=12)
    t.raise_for_status()
    usd=float(t.json()["price"])
    r=requests.get("https://api.exchange.coinbase.com/products/BTC-USD/candles",params={"granularity":300,"start":now-90000,"end":now},headers=h,timeout=12)
    r.raise_for_status()
    rows=r.json()
    if len(rows)<35: raise ValueError("Coinbase से पर्याप्त candle data नहीं मिला।")
    d=pd.DataFrame(rows,columns=["time","low","high","open","close","volume"])
    d["time"]=pd.to_datetime(d["time"],unit="s",utc=True)
    for c in ["low","high","open","close","volume"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    d["ema9"]=d.close.ewm(span=9,adjust=False).mean()
    d["ema21"]=d.close.ewm(span=21,adjust=False).mean()
    delta=d.close.diff()
    gain=delta.clip(lower=0).rolling(14).mean()
    loss=(-delta.clip(upper=0)).rolling(14).mean()
    d["rsi"]=(100-100/(1+gain/loss.replace(0,np.nan))).fillna(50)
    cg=requests.get("https://api.coingecko.com/api/v3/simple/price",params={"ids":"bitcoin","vs_currencies":"inr"},headers=h,timeout=12)
    cg.raise_for_status()
    inr_btc=float(cg.json()["bitcoin"]["inr"])
    fx=inr_btc/usd
    last=d.iloc[-1]
    return {"df":d,"usd":usd,"inr":usd*fx,"fx":fx,"rsi":float(last.rsi),"ema9":float(last.ema9),"ema21":float(last.ema21),"candle":str(last.time),"at":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

defaults={"cash":START_CASH,"pos":None,"trades":[],"day_pnl":0.0,"pnl_date":date.today().isoformat(),"last_candle":None,"m":None,"notice":"पहली बार Scan करें।"}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v
if st.session_state.pnl_date!=date.today().isoformat():
    st.session_state.pnl_date=date.today().isoformat(); st.session_state.day_pnl=0.0

st.subheader("Auto Scan")
auto=st.toggle("🤖 Auto Scan चालू करें (लगभग हर 1 मिनट)",value=False)
if auto:
    from streamlit_autorefresh import st_autorefresh
    ticks=st_autorefresh(interval=60000,limit=None,key="bg_crypto_v14_refresh")
else: ticks=0
manual=st.button("🔄 Fetch Live BTC Data & Scan",type="primary",use_container_width=True)
scan=manual or (auto and ticks>0)

def signal(m):
    d=m["df"]
    up=m["ema9"]>m["ema21"] and 40<=m["rsi"]<=60 and d.close.iloc[-1]>d.close.iloc[-2]
    down=m["ema9"]<m["ema21"] and 35<=m["rsi"]<=55 and d.close.iloc[-1]<d.close.iloc[-2]
    return "BUY" if up else ("SHORT" if down else "WAIT")

def close_trade(m,reason):
    p=st.session_state.pos
    px=m["inr"]
    pnl=(px-p["entry"])*p["qty"] if p["side"]=="BUY" else (p["entry"]-px)*p["qty"]
    st.session_state.cash += p["stake"]+pnl
    st.session_state.day_pnl += pnl
    st.session_state.trades.append({"Entry UTC":p["time"],"Exit UTC":m["at"],"Side":p["side"],"Entry ₹":round(p["entry"],2),"Exit ₹":round(px,2),"BTC":round(p["qty"],8),"P&L ₹":round(pnl,2),"Reason":reason})
    st.session_state.pos=None
    st.session_state.notice=f"{p['side']} Paper position बंद • {reason} • P&L ₹{pnl:.2f}"

if scan:
    try:
        m=market_data(); st.session_state.m=m
        sig=signal(m); p=st.session_state.pos
        if p:
            pnl=(m["inr"]-p["entry"])*p["qty"] if p["side"]=="BUY" else (p["entry"]-m["inr"])*p["qty"]
            if pnl>=TARGET: close_trade(m,"₹5 Profit Target")
            elif pnl<=-STOP: close_trade(m,"₹25 Stop Loss")
            else: st.session_state.notice=f"{p['side']} खुला है • Unrealized P&L ₹{pnl:.2f}"
        if st.session_state.pos is None and sig in ("BUY","SHORT"):
            if st.session_state.day_pnl<=-DAILY_LIMIT:
                st.session_state.notice="Daily loss limit ₹50 पूरी; नया trade बंद।"
            elif st.session_state.last_candle!=m["candle"]:
                stake=min(MAX_STAKE,st.session_state.cash)
                qty=min(RISK/(m["inr"]*0.01),stake/m["inr"])
                used=qty*m["inr"]
                if qty>0 and used<=st.session_state.cash:
                    st.session_state.cash-=used
                    st.session_state.pos={"side":sig,"entry":m["inr"],"qty":qty,"stake":used,"time":m["at"]}
                    st.session_state.last_candle=m["candle"]
                    st.session_state.notice=f"Automatic Paper {sig} खुला • Target ₹5 • Stop ₹25"
        elif st.session_state.pos is None and sig=="WAIT":
            st.session_state.notice="अभी Entry Signal नहीं है। WAIT करें।"
    except Exception as e:
        st.session_state.notice=f"Market data error: {e}"

m=st.session_state.m
if m:
    sig=signal(m); p=st.session_state.pos
    unreal=0.0; invested=0.0
    if p:
        invested=p["stake"]
        unreal=(m["inr"]-p["entry"])*p["qty"] if p["side"]=="BUY" else (p["entry"]-m["inr"])*p["qty"]
    equity=st.session_state.cash+invested+unreal
    st.subheader("Market Snapshot")
    a,b,c,d=st.columns(4)
    a.metric("BTC/USD",f"${m['usd']:,.2f}"); b.metric("BTC INR approx",f"₹{m['inr']:,.0f}")
    c.metric("RSI",f"{m['rsi']:.1f}"); d.metric("USD/INR approx",f"{m['fx']:.2f}")
    st.write(f"EMA9: ${m['ema9']:,.2f} | EMA21: ${m['ema21']:,.2f}")
    st.subheader("AI Signal"); st.write(f"**{sig}**"); st.info(st.session_state.notice)
    st.subheader("Paper Account")
    a,b,c=st.columns(3)
    a.metric("Free Virtual Cash",f"₹{st.session_state.cash:,.2f}")
    b.metric("Open Position","YES" if p else "NO")
    c.metric("Total Virtual Equity",f"₹{equity:,.2f}")
    a,b,c=st.columns(3)
    a.metric("Daily Realized P&L",f"₹{st.session_state.day_pnl:,.2f}")
    b.metric("Unrealized P&L",f"₹{unreal:,.2f}")
    c.metric("Invested Stake",f"₹{invested:,.2f}")
    if p: st.write(f"Open {p['side']} • Entry ₹{p['entry']:,.2f} • ₹5 target / ₹25 stop")
    st.line_chart(m["df"].set_index("time")[["close","ema9","ema21"]].tail(100))
    st.caption(f"Last scan: {m['at']}")
else: st.info(st.session_state.notice)

st.subheader("Rules")
st.write("₹5,000 virtual capital • Max stake ₹2,500 • Risk budget ₹25 • Profit target ₹5 per closed trade • Stop loss ₹25 • Daily loss limit ₹50.")
st.write("Buy-the-Dip LONG and Downtrend SHORT are rule-based paper simulations; one position at a time.")
st.caption("यह हर सेकंड ट्रेड नहीं करता। Auto Scan लगभग हर 1 मिनट में live ticker पढ़ता है, जबकि indicators 5-minute candles से बनते हैं। ₹5 target guaranteed नहीं है; fees/slippage नहीं जोड़े गए। Public APIs rate-limit कर सकती हैं। Session restart पर account/history reset हो सकते हैं।")
st.subheader("Closed Paper Trades")
if st.session_state.trades: st.dataframe(pd.DataFrame(st.session_state.trades),use_container_width=True,hide_index=True)
else: st.write("अभी कोई बंद Paper Trade नहीं है।")
if st.button("Reset Paper Account"):
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()
