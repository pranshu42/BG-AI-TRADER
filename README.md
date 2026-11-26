# BG AI CRYPTO TRADER v1.4
BTC paper simulator with Buy the Dip LONG and Downtrend SHORT signals.
- ₹5 profit target per completed paper trade (not guaranteed)
- ₹25 stop loss per trade; ₹50 daily realized loss limit
- ₹5,000 virtual capital; ₹2,500 maximum stake
- Auto Scan approximately once per minute while page remains open/active
- Uses Coinbase BTC-USD public ticker/candles and approximate INR conversion
- No real orders, API keys, futures, or leverage

Update existing GitHub repository by extracting this ZIP and replacing app.py, requirements.txt and README.md. Commit changes, then wait for Streamlit Cloud to redeploy.

Limitations: Not a 24/7 bot; not second-by-second trading. Entry indicators use 5-minute candles. Public APIs can fail/rate-limit. Fees/slippage are not modelled. Streamlit session state can reset after sleep/restart. Paper trading only; no profit guarantee or investment advice.
