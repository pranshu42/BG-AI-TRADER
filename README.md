# BG AI CRYPTO TRADER v1.1 — Fixed

Bitcoin (BTC) spot-style paper trading simulator. No real orders, no exchange login, no API keys.

## Files
- `app.py`
- `requirements.txt`

## Deploy/update the existing GitHub repository
1. Extract this ZIP on your phone/computer.
2. In your existing `BG-AI-TRADER` GitHub repository, replace the old `app.py` and `requirements.txt` with these files.
3. Commit the changes.
4. Streamlit Community Cloud should redeploy the existing app. Refresh the app after deployment.

## What was fixed
- Account metrics are displayed after the BUY/SELL action, so cash and open-position status update immediately.
- Free cash, invested stake, total virtual equity, realized P&L, and unrealized P&L are shown separately.
- An open position is managed before any new entry; the app will not open a second position while one is active.
- Daily realized P&L resets when the calendar date changes within the active session.

## Strategy / safety
- Coinbase public BTC-USD 5-minute candles.
- EMA 9 / EMA 21 and RSI filter.
- Starting virtual capital: INR 5,000.
- Risk budget: up to INR 25 per trade; max stake INR 2,500.
- Stop loss: 1%; target: 2%.
- Daily realized loss limit: INR 50.
- Long-only, no leverage, no short selling, no real trades.

## Important limitations
- Scan is manual; this is not a 24x7 background bot.
- Public data feeds may be unavailable or rate-limited.
- INR BTC price is estimated from public BTC/INR and BTC/USD values.
- Streamlit Cloud session state can reset on app sleep/restart. This version does not provide durable trade storage.
- Paper results are simulations, not profit guarantees or investment advice.
