# BG AI CRYPTO TRADER v1.2 — AUTO SCAN

BTC spot-style paper trading only. No real exchange orders, API keys, leverage, or short selling.

## Update your existing GitHub repository
1. Extract this ZIP.
2. In the existing `BG-AI-TRADER` repository, replace `app.py` and `requirements.txt` with these versions.
3. Commit the changes.
4. Wait for Streamlit Community Cloud to redeploy, then refresh your existing app.

## Auto Scan
- Turn on **Auto Scan चालू करें (हर 1 मिनट)** to fetch market data and evaluate the strategy once per minute.
- Auto Scan works only while the Streamlit app page remains open and active in the browser. It is not a 24/7 cloud background bot; mobile browsers may pause background tabs or sleep.
- You can still use the manual Fetch button when Auto Scan is off.

## Trading rules
- Coinbase public BTC-USD 5-minute candles.
- EMA 9 / EMA 21 + RSI filter.
- Starting virtual capital ₹5,000.
- Risk budget up to ₹25 per trade; max stake ₹2,500.
- Stop loss 1%; target 2%; daily realized loss limit ₹50.
- Paper trading only. Results are simulated and not profit guarantees.

## Limitations
- Public data APIs may be unavailable or rate-limited.
- INR BTC price is estimated from public BTC/INR and BTC/USD values.
- Streamlit session state may reset on app restart/sleep. This app does not provide durable trade storage.
- Auto Scan is not guaranteed to run while the phone is locked or the browser tab is in the background.
