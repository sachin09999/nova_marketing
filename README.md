# 🚀 NovaBorrow Automated Marketing Suite

Independent marketing automation toolkit for NovaBorrow.

---

## 📁 Modules

### 1. `marketing-bot/` (YouTube Comment Bot)
- **Features:** Multi-account auto-failover, concurrent commenting with unique comments per account, zero-quota public search fallback, anti-spam randomized delays.
- **Run:**
  ```bash
  python3 marketing-bot/youtube_comment_bot.py
  ```

### 2. `shorts-generator/` (Faceless Shorts & Reels Generator)
- **Features:** 100% Free Microsoft Azure Hindi AI voiceover (`hi-IN-MadhurNeural`), auto-synced burned subtitles, 1080x1920 fintech card branding.
- **Run:**
  ```bash
  python3 shorts-generator/generate_shorts.py --all
  ```

### 3. `telegram-bot/` (Telegram Assistant & Broadcast Bot)
- **Features:** 24x7 interactive customer loan eligibility checker, automated channel marketing broadcasts to [@novaborrow](https://t.me/novaborrow).
- **Run:**
  ```bash
  # Live 24x7 Assistant
  python3 telegram-bot/bot.py --listen

  # Broadcast to channel
  python3 telegram-bot/bot.py --broadcast
  ```
