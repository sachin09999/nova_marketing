# 🚀 NovaBorrow Automated Video Marketing Bot

Ye automation tool YouTube par loan-related videos (e.g. *"best loan app"*, *"instant personal loan"*, *"low cibil loan"*) ko target karke automated, organic-looking promotional comments post karne ke liye banaya gaya hai.

---

## 📌 Features

1. **Official YouTube Data API v3:** Google ke official secure OAuth 2.0 protocol ke sath chalta hai.
2. **Anti-Spam Spintax Generator:** Har comment me greetings, marketing pitch aur closing lines randomly mix hoti hain taaki YouTube algorithm duplicate comment samajh kar block/shadowban na kare.
3. **Smart Duplicate Prevention:** Commented videos ko `history.json` me store karta hai taaki ek video par dobara comment na ho.
4. **Safety Delays:** Har comment ke beech 45 se 90 seconds ka random delay deta hai taaki bot-like activity detect na ho.
5. **Dry-Run Mode:** Bina comment post kiye testing aur preview karne ki suvidha (`--dry-run`).
6. **Multi-Account Concurrent Commenting:** Har target video par aapke saare configured accounts (e.g. Account 1, 2, 3) alag-alag unique comments post karte hain with anti-spam spacing!
7. **Quota Exhaustion Auto-Protection:** Agar kisi account ka daily quota (10,000 units) reach ho jaye, toh remaining accounts bina ruke process ko continue rakhte hain!

---

## ⚠️ Important Note regarding Instagram

> **Meta / Instagram Policy:**
> Instagram ki Official Graph API kisi aur user ke public Reels/Posts par third-party automated comments post karne ki permission **strictly allow nahi karti** (API policy violation & spam prevention).
> 
> Official API se Instagram par sirf aapke *apne account* ke posts/comments ko manage kiya ja sakta hai.
> Isliye official API ke zariye **YouTube Data API v3** hi best aur safest method hai.

---

## 🛠️ Step 1: Google Cloud Setup (One-time)

1. [Google Cloud Console](https://console.cloud.google.com/) par jayein aur ek new project banayein (e.g. `NovaBorrow-Marketing`).
2. Left menu me **APIs & Services > Library** par jayein.
3. Search karein **YouTube Data API v3** aur **Enable** par click karein.
4. **OAuth consent screen** par jayein:
   - User Type: **External** select karein.
   - App Name enter karein aur apna Gmail ID dalein.
   - **Test users** section me apna wahi Google Account add karein jisse aap YouTube comment post karna chahte hain.
5. **Credentials** tab par jayein:
   - Click: **Create Credentials > OAuth client ID**
   - Application type: **Desktop app** select karein.
   - Click **Create**.
6. Jo credentials bane, uska JSON file download karein aur uska naam rename karke **`client_secret.json`** rakh kar is folder me copy karein:
   `/home/dts-sachin/Desktop/APP_scheme/NovaBorrow/scripts/marketing-bot/client_secret.json`

---

## 🚀 Step 2: How to Run

### 1. Dry Run (Test Mode - Without Posting)
Ye command check karegi ki setup kaisa kaam kar raha hai bina kisi video par comment post kiye:
```bash
python3 scripts/marketing-bot/youtube_comment_bot.py --dry-run
```

### 2. 🚀 Ultimate Hybrid / Combo Mode (Video Comments + Lead Auto-Reply Ek Saath)
Is mode me bot har target video par **aapke teeno accounts se 3 unique comments** bhi post karega, aur usi video ke comment box me **loan seekers ko auto-reply** bhi kar dega:
```bash
python3 youtube_comment_bot.py --hybrid --public-search
```
*(Bina comment post kiye check karne ke liye: `python3 youtube_comment_bot.py --hybrid --dry-run`)*

### 3. Live Run (Sirf Video Comments)
```bash
python3 youtube_comment_bot.py --public-search --limit 25
```

### 3. Category 1: 🎯 Instant Traffic — Loan Seeker Lead Reply Bot (Highest Conversion ⭐⭐⭐⭐⭐)
Finance YouTubers ke comments scan karke directly loan seekers ko auto-reply karta hai (Notification direct seeker ke phone par jata hai):
```bash
# Automated Search + Scan + Reply
python3 youtube_comment_bot.py --reply-leads --public-search

# Specific Video ke comments scan karke loan seekers ko reply karna
python3 youtube_comment_bot.py --reply-leads --url "https://www.youtube.com/watch?v=VIDEO_ID"

# Test/Preview Mode (Bina comment post kiye check karne ke liye)
python3 youtube_comment_bot.py --reply-leads --dry-run
```

### 4. Kisi Direct Video / Reel / Short par Comment Post Karna (⚡ Sabse Fast)
Agar aapke paas koi YouTube video ka link hai to bina kisi search ke direct comment post karein:
```bash
python3 youtube_comment_bot.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

### 4. High-View aur Popular Videos Target Karna
Pehle sirf newly uploaded videos search hoti thi. Ab aap relevance ya most viewed videos search kar sakte hain:
```bash
python3 scripts/marketing-bot/youtube_comment_bot.py --order relevance --days 90 --limit 10
python3 scripts/marketing-bot/youtube_comment_bot.py --order viewCount --days 90 --limit 10
```

### 5. Specific Keyword Target Karna
```bash
python3 scripts/marketing-bot/youtube_comment_bot.py --keyword "kreditbee loan app" --limit 5
```

### 6. Comment History Ignore Ya Reset Karna
- **History Ignore Karna (Duplicate check bypass karke comment karna):**
  ```bash
  python3 scripts/marketing-bot/youtube_comment_bot.py --ignore-history --limit 5
  ```
- **History Reset Karna (Purani history ka auto-backup ban jayega):**
  ```bash
  python3 scripts/marketing-bot/youtube_comment_bot.py --clear-history -y
  ```

### 7. Past History Check Karna
Kitne videos par comment ho chuka hai dekhne ke liye:
```bash
python3 scripts/marketing-bot/youtube_comment_bot.py --history
```

---

## 💡 "0 Comments Processed" Kyun Aata Hai Aur Iska Solution:

Agar bot run karne par `Total comments processed: 0` aaye, to iske 2 mukhya kaaran ho sakte hain:

1. **Purani History (Duplicate Prevention):**
   Bot ne pichle runs me 290+ videos par pehle hi comment kar diya hai (`history.json` me recorded hai). Isliye woh unhe skip kar deta hai.
   - **Solution:** `--order relevance`, `--order viewCount`, ya `--days 90` lagakar run karein, ya `--clear-history -y` se history reset karein.

2. **Google Cloud Daily Quota (10,000 units):**
   YouTube API free tier me roz 10,000 units milte hain (1 Search call = 100 units). Agar din me 100 search ho chuki hain to search temporarily pause ho jata hai.
   - **Solution:** 
     - `--url "https://www.youtube.com/watch?v=..."` use karein (Direct URL me search quota nahi lagta!).
     - Ya Google Cloud Console me ek aur project banakar uska `client_secret.json` daal dein (turant 10,000 fresh units mil jayenge).
     - Quota automatically daily (midnight Pacific Time, ~1:30 PM IST) reset ho jata hai.

---

## ⚙️ Configuration (`config.json`)

Aap [config.json](file:///home/dts-sachin/Desktop/APP_scheme/NovaBorrow/scripts/marketing-bot/config.json) me:
- **Keywords** badal sakte hain (ab 60+ curated loan keywords shamil hain).
- **Comment variations** (greetings, pitches, NovaBorrow benefits) customize kar sakte hain.
- **Delays** aur **daily limits** set kar sakte hain.

---

## 🛡️ Best Practices for Account Safety
- Ek din me 10-15 se zyada comments post na karein.
- Daily runs ke beech gap rakhein.
- Apne comments ko genuine aur helpful rakhein taaki video creator ya viewers comment ko report na karein.

