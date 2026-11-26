# BG AI TRADER v1.3 — India NSE Only

## What changed
- India NSE cash-equity watchlist only.
- ₹5,000 virtual capital.
- Max 2 new simulated BUYs per day.
- Planned stop-loss risk capped at ₹25 per trade using whole-share quantity.
- If even one share exceeds the risk budget, the BUY is skipped.
- Daily realized loss limit ₹50.
- Paper stop/target exits are evaluated on a subsequent manual scan.
- Trade history CSV export.

## Strategy
Daily EMA 9/21 trend, RSI(14) between 50 and 68, and latest daily volume at/above 20-day average.

## Important limitations
- Educational paper trading only; no Navia API and no live orders.
- Yahoo Finance daily data may be delayed, incomplete or unavailable.
- Scan and simulated exits run only when the user presses the scan button; not 24/7.
- Stop/target checks use available daily data, not live intraday ticks.
- The JSON state file is local runtime convenience only. Streamlit Community Cloud may clear it on restart/redeploy. Download the CSV history regularly. A persistent cloud database (e.g. Supabase) must be configured separately for reliable long-term records.
- No profit guarantee. This is a simple rules-based strategy, not validated predictive AI.
