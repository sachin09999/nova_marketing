# 🚀 NovaBorrow Marketing Bot - 24/7 Cloud Deployment & Web Dashboard Guide

## ⚠️ Important Note: Vercel vs 24/7 Cloud Platforms

### Vercel par Bot kyu nahi chal sakta?
Aapne poocha tha ki **"jab laptop band karta hu to script band ho jati hai to Vercel par deploy karna hai"**:
- **Vercel ek Serverless Platform hai** (Next.js aur Static frontends ke liye design kiya gaya hai).
- Serverless me har request ki maximum execution limit **10 se 60 seconds** hoti hai.
- Vercel me koi background process ya continuous loop (`while True`) 24/7 nahi chal sakti. Jaise hi request khatam hoti hai ya 30-60 seconds hote hain, Vercel script ko forcefully band (kill) kar deta hai.

### Sahi Solution: 24/7 Cloud Platforms (Laptop band hone par bhi chalta rahega)
Script ko **24 ghante bina laptop on rakhe** chalane ke liye aisi services chahiye jahan background daemon / container hamesha active rahe:
1. **Render.com** (Recommended - Free Web Service / Container)
2. **Railway.app** (1-Click Docker Deploy)
3. **VPS (Virtual Private Server)**: $3-$4/month ka Linux server (DigitalOcean, Hetzner, AWS EC2, ya Oracle Cloud Free Tier).

---

## 🖥️ Local System par Web Dashboard kaise chalayein?

Aapke local machine par web dashboard abhi **READY** hai:

```bash
cd /home/dts-sachin/Desktop/APP_scheme/NovaBorrow-Marketing
python3 server.py
```

Browser me open karein:
👉 **`http://localhost:8080`**

### 🔑 Login Credentials:
- **Username:** `admin`
- **Password:** `novaborrow2026`

*(Aap chahein to `DASHBOARD_PASS` environment variable se ise change kar sakte hain).*

---

## 🌐 24/7 Free Cloud Deployment Steps (Render.com)

Jab aap Render par deploy kar denge, to **laptop switch off karne ke baad bhi bot 24/7 internet par chalta rahega**:

### Step 1: GitHub par Repository Push karein
```bash
git add .
git commit -m "Add Web Dashboard and 24/7 cloud runner"
git push origin main
```

### Step 2: Render.com par account banayein & New Web Service create karein
1. [Render.com](https://render.com) par free account banayein.
2. Dashboard me **"New +"** button par click karke **"Web Service"** select karein.
3. Apna GitHub repo connect karein (`NovaBorrow-Marketing`).
4. Settings choose karein:
   - **Environment:** `Python 3` (ya Docker)
   - **Build Command:** `pip install -r marketing-bot/requirements.txt aiohttp requests`
   - **Start Command:** `python3 server.py`
   - **Plan:** `Free`
5. **Environment Variables** add karein:
   - `PORT`: `8080`
   - `DASHBOARD_USER`: `admin`
   - `DASHBOARD_PASS`: `apna_custom_password`
   - `SUPABASE_DB_URL`: `postgresql://postgres:%2339DGAKT%23eMbjNg@db.uhgzgbkovachkdiaudfx.supabase.co:5432/postgres`
6. **"Deploy Web Service"** par click karein!

Kuch hi minutes me aapko ek public URL mil jayega (e.g. `https://novaborrow-marketing.onrender.com`).
Ab aap kisi bhi mobile ya computer se browser me URL open karke bot control kar sakte hain, aur **laptop band karne par bhi bot chalta rahega**!

---

## 🎯 Web Dashboard Features

### 1. Multiple YouTube JSON Upload (Drag & Drop)
- Dashboard me **"Upload YouTube Credentials"** box hai.
- Aap ek saath multiple `client_secret*.json` aur unke `token*.pickle` files select ya drag & drop kar sakte hain.
- System automatically file parse karke account list me add kar deta hai.

### 2. Checkmark (Tick) Selection (1, 2, ya 3 Accounts)
- Har account ke aage ek **Neon Checkbox** diya gaya hai.
- Aap apni preference ke hisab se kisi bhi account par **tick ya untick** kar sakte hain:
  - **1 Account (Solo Mode):** Only 1 account selected.
  - **Top 3 Accounts (Hybrid Combo Mode):** 3 accounts selected (Recommended for maximum reach!).
  - **Custom Selection:** Kisi bhi 1, 2, 3 ya sabhi accounts ko tick karein.
- Quick buttons bhi hain:
  - `⚡ Select Top 3 (Hybrid)`
  - `Select 1 (Solo)`
  - `Select All`
  - `Clear All`

### 3. Google OAuth Login Button
- Agar kisi account ka token expire ya missing hai, to uske aage **"🔐 Login Google"** button dikhega.
- Click karne par modal khulega jisme:
  1. Google Auth link par click karke login karke permissions grant karein.
  2. Code / Redirect URL ko modal me paste karke **"Save & Authenticate"** karein.
  3. Token automatically generate ho jayega!

### 4. Bot Execution Control
- **Execution Modes:**
  - `🚀 Hybrid Combo`: 3 Accounts se video par comment karega + loan mangne walo ko auto-reply karega.
  - `💬 Lead Seeker Only`: Comments scan karke direct loan seekers ko reply karega.
  - `📝 Standard Comments`: Keyword search wali top videos par natural comments post karega.
- **Toggles:**
  - `⚡ Zero-Quota Public Search`: Free search mode jo API quota waste nahi karta.
  - `🔄 Ignore Past History`: Purani videos par dobara comment karne ke liye.
- **Controls:**
  - Max comments per run, Delay time (seconds), Target custom keywords.
  - Big Glowing **"START BOT"** & **"STOP BOT"** buttons.

### 5. Live Real-Time Terminal Log Stream
- Bottom me real-time dark terminal console diya gaya hai (WebSocket powered).
- Real-time me dikhega:
  - Kaunsi video search ho rahi hai.
  - Kaunse account se comment post hua.
  - Quota status aur delay timers.
- Auto-scroll, Copy Logs, aur Clear Terminal ke options included hain.
