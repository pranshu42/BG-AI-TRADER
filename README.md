# BG AI CRYPTO TRADER v1.3 — Buy the Dip + Short Paper Simulation

- BTC only, Coinbase public BTC-USD 5-minute candles.
- Buy-the-Dip LONG: bullish EMA trend plus green/recovery candle and RSI confirmation.
- SHORT simulation: bearish EMA trend and weak RSI. This is only an internal paper simulation, not exchange Futures trading.
- Auto Scan every 1 minute while the app page remains open and active.
- Starting virtual capital ₹5,000; max stake ₹2,500; risk budget up to ₹25 per trade.
- Stop Loss 1%, Target 2%, daily realized loss limit ₹50.
- No real orders, no API keys, no leverage, no short order sent to any exchange.

## Update existing GitHub repository
Extract this ZIP and replace `app.py`, `requirements.txt`, and `README.md` in the existing `BG-AI-TRADER` repository. Commit changes and wait for Streamlit redeploy.

## Important limitations
Auto Scan may pause if the phone locks, browser backgrounds the page, or Streamlit sleeps/restarts. Session-based paper account data can reset after restart. Public market-data APIs can be delayed/rate-limited. This is a simple rule-based educational simulator, not financial advice or a profit guarantee.
