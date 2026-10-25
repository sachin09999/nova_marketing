# 🎬 NovaBorrow 100% Automated Faceless Shorts & Reels Generator

100% Free, zero-ban risk automated short-form video marketing generator for **YouTube Shorts**, **Instagram Reels**, **ShareChat**, and **Moj**.

---

## ✨ Features
1. **100% Free Natural Hindi AI Voiceover:** Microsoft Azure Neural Speech (`hi-IN-MadhurNeural` Male / `hi-IN-SwaraNeural` Female) bina kisi paid API key ke.
2. **Auto-Synced Subtitles:** Modern dynamic subtitles burned directly onto the video in the safe viewing zone.
3. **Fintech Branding Card:** High-contrast, clean 9:16 vertical card with NovaBorrow features (`₹5,000 - ₹50,000`, `Low CIBIL Accepted`, `15 Min Approval`).
4. **Zero Ban Risk:** Original content creation — algorithms naturally recommend informative finance shorts.
5. **Ready-to-Copy Metadata:** Har video ke sath Title, Caption aur Viral Hashtags automatically generate hote hain.

---

## 🚀 How to Run

### 1. View all pre-built viral scripts:
```bash
python3 scripts/shorts-generator/generate_shorts.py --list
```

### 2. Generate a random short video:
```bash
python3 scripts/shorts-generator/generate_shorts.py
```

### 3. Generate a specific short (e.g. Low CIBIL topic):
```bash
python3 scripts/shorts-generator/generate_shorts.py --script low_cibil_secret
```

### 4. Generate with Female Voice:
```bash
python3 scripts/shorts-generator/generate_shorts.py --script top_3_apps --voice female
```

### 5. Generate ALL viral scripts in one click:
```bash
python3 scripts/shorts-generator/generate_shorts.py --all
```

All generated MP4 videos will be saved inside:
`scripts/shorts-generator/output/`

---

## 📝 Adding New Scripts
Aap naye topics ya scripts add karne ke liye simply `scripts/shorts-generator/config.json` me naya object add kar sakte hain:
```json
{
  "id": "my_new_topic",
  "title": "Topic Name",
  "hook": "First 3 seconds scroll-stopping question in Hindi?",
  "body": "Value content explaining the loan tips and introducing NovaBorrow.",
  "cta": "Call to action urging users to check the link in bio or comments."
}
```
