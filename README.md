# BG AI TRADER v1.0 — Paper Trading

यह शुरुआती Streamlit ऐप केवल paper trading अभ्यास के लिए है।

## इसमें क्या है
- ₹5,000 का virtual starting cash
- Manual simulated BUY/SELL orders
- Positions और trade history
- प्रति BUY ₹25 planned-risk check
- प्रति दिन ₹50 realized-loss stop
- अधिकतम 2 paper trades/day
- CSV history export

## जरूरी सीमाएँ
- यह Navia API से कनेक्ट नहीं है।
- इसमें live market prices नहीं आते; execution price आप स्वयं भरते हैं।
- Stop Loss/Target अभी केवल रिकॉर्ड होते हैं, auto-trigger नहीं।
- ऐप रीस्टार्ट होने पर session data मिट सकता है।
- यह निवेश सलाह नहीं है और मुनाफे की गारंटी नहीं देता।
- Live trading कोड/बटन शामिल नहीं है।

## Cloud पर मुफ्त demo deploy
1. GitHub पर नया repository बनाइए: `bg-ai-trader`
2. इस ZIP की तीनों फाइलें repository में upload कीजिए: `app.py`, `requirements.txt`, `README.md`
3. https://share.streamlit.io खोलिए और GitHub से sign in कीजिए।
4. Create app चुनिए।
5. Repository: `bg-ai-trader`, Branch: `main`, Main file path: `app.py`
6. Deploy दबाइए।

Streamlit Community Cloud free hosting देता है, लेकिन यह हमेशा चालू रहने वाले production trading server या persistent database का विकल्प नहीं है। इस paper demo में session data restart पर खो सकता है।

## Navia API
Navia API credentials अभी न डालें। Live integration से पहले Navia से लिखित रूप में API onboarding, static IP, OAuth/2FA, algo tagging/registration और applicable exchange requirements confirm करें।
