# BG AI TRADER v1.5 — India Paper Trading

## Included
- NSE intraday paper-trade journal
- NIFTY, BANKNIFTY and selected stock-options paper journal (CE/PE)
- Manual verified entry/exit price, strike, expiry and lot size
- Per-trade planned risk check (₹25), daily realized loss guard (₹50)
- Maximum 2 new trades per day
- SQLite trade history and CSV export

## Important limitations
- Paper trading only. No broker connection and no live order execution.
- This build does not fetch live NSE option-chain data or option premiums.
- Enter contract expiry, strike, lot size and premium only after verifying them from a reliable exchange/broker source.
- Prices and stop/target are not monitored in the background. The user must manually enter an exit price.
- Brokerage, taxes, slippage, margin, exercise/assignment and expiry settlement are not modelled.
- Streamlit Community Cloud local SQLite storage may not be durable across app rebuilds/restarts. Download CSV backups regularly. For durable cloud storage, configure an external database separately.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Upload `app.py`, `requirements.txt`, and `README.md` to the `main` branch of your GitHub repository.
2. In Streamlit Community Cloud, select repository `pranshu42/BG-AI-TRADER`.
3. Set branch to `main` and main file path to `app.py`.
4. Deploy / wait for the app to reboot.

If your existing repository has an `app.py`, replace it only after keeping a backup of the old version.
