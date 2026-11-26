# BG AI TRADER v1.1 — Auto Paper Trading

## Features
- ₹5,000 virtual capital
- India + USA sample watchlist
- Daily historical data scan using Yahoo Finance (`yfinance`)
- Swing strategy: EMA 9/21, RSI(14), volume confirmation
- Automatic paper BUY on button press, max 2 new buys/day
- Simulated stop-loss/target exits checked on subsequent scans
- Positions, trade history, CSV export

## Important limitations
- Paper trading only; no Navia API or live order execution.
- Yahoo Finance data can be delayed, incomplete, or unavailable; it is not an official exchange feed.
- The scanner runs only when the user presses the scan button, not 24/7 in the background.
- Positions and history are held in Streamlit session state and may be lost on app restart/session reset.
- Stop/target exits are checked only when a new scan is run, at the latest downloaded daily close.
- The strategy is a simple educational rule set, not a validated predictive AI and does not guarantee profit.
- No F&O or leverage.

## Deploy update
Upload/replace `app.py`, `requirements.txt`, and `README.md` in the existing GitHub repository. Streamlit Community Cloud will redeploy after commit.
