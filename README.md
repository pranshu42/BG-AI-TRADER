# BG AI CRYPTO TRADER v1.3.1 — DISPLAY FIX

This version keeps both paper strategies:
- Buy-the-Dip LONG simulation
- Downtrend SHORT simulation

It renders trade status using a normal explicit Streamlit `if/else` alert and prevents a position from closing and reopening/reversing on the same 5-minute candle.

## Update your existing GitHub repository
1. Extract this ZIP.
2. Replace `app.py`, `requirements.txt`, and `README.md` in your existing `BG-AI-TRADER` repository.
3. Commit changes.
4. Wait for Streamlit Community Cloud to redeploy, then refresh the app.

## Paper-only risk settings
- Virtual starting capital: ₹5,000
- Risk budget: up to ₹25 per trade
- Maximum stake: ₹2,500
- Stop loss: 1%; target: 2%
- Daily realized loss limit: ₹50
- No exchange API keys, real orders, futures, or leverage.

Auto Scan runs only while the Streamlit page remains open and active. It is not a 24/7 background bot. Streamlit session state may reset after a restart/sleep. Public market data may be unavailable or rate-limited. This is a simulation, not a profit guarantee or investment advice.
