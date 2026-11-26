# BG AI CRYPTO TRADER v1.0

BTC Spot-style PAPER trading only. No exchange credentials and no real orders.

## Files
- app.py
- requirements.txt

## Deploy on Streamlit Community Cloud
1. Create a new GitHub repository (or a separate branch/repository).
2. Upload `app.py` and `requirements.txt`.
3. In Streamlit Community Cloud, deploy `app.py`.
4. Press **Fetch Live BTC Data & Scan** to fetch public market data and run one paper scan.

## Market data
- Coinbase Exchange public BTC-USD 5-minute candles (no API key).
- CoinGecko public BTC-INR price used to estimate USD/INR conversion.
- Public data availability, rate limits and geographic access can change.

## Strategy (starter rules, not financial advice)
- EMA 9 / EMA 21 trend filter.
- RSI 14 confirmation.
- Spot-style long-only paper position.
- ₹5,000 virtual starting capital.
- Maximum ₹25 risk budget per trade, 1% stop, 2% target.
- ₹50 daily realized loss stop.

## Important limitations
- This is a starter simulator, not a continuously running 24/7 unattended bot.
- The scan runs when the user presses the scan button; exits are checked on subsequent scans.
- Streamlit Community Cloud may sleep/restart; session paper history may be lost.
- INR conversion is estimated from public BTC-INR and BTC-USD prices and may differ from actual FX.
- No private keys, exchange account, or real order placement are used.
- No profit is guaranteed. Test extensively before considering any real-money use.
