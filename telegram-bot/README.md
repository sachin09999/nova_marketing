# 🤖 NovaBorrow Telegram Assistant & Marketing Bot

Telegram bot for 24x7 customer support, interactive loan eligibility check, and channel broadcast marketing.

---

## ⚡ Bot Details
* **Bot Link:** [t.me/novaborrow_official_bot](https://t.me/novaborrow_official_bot)
* **Username:** `@novaborrow_official_bot`

---

## 🚀 Features & Usage

### 1. Interactive 24x7 Customer Loan Assistant
Jab bhi koi user Telegram par `@novaborrow_official_bot` ko `/start` bhejega ya message karega, bot unhe turant buttons ke sath reply karega:
* 🚀 **Apply Online (Direct Link)**
* 📊 **Check Loan Eligibility (Instant 5-second check)**
* 📈 **Low CIBIL Tips (How to get approved at 550 CIBIL)**
* ❓ **FAQs & Transparency (Zero upfront fees)**

**Run Assistant:**
```bash
python3 scripts/telegram-bot/bot.py --listen
```

---

### 2. Telegram Channel Daily Marketing Broadcast
Aap apne Telegram Channel par automated loan tips aur NovaBorrow ke marketing links post kar sakte hain.

1. Apne channel me `@novaborrow_official_bot` ko **Admin** banayein.
2. Channel username save karein (e.g. `@novaborrow_updates`):
   ```bash
   python3 scripts/telegram-bot/bot.py --set-channel @your_channel_name
   ```
3. Daily tips broadcast karein:
   ```bash
   python3 scripts/telegram-bot/bot.py --broadcast
   ```
