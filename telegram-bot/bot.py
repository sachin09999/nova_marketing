#!/usr/bin/env python3
"""
NovaBorrow 100% Free Automated Telegram Assistant & Marketing Bot
Features:
1. 24x7 Interactive Loan Eligibility Assistant (resizes to loan application)
2. Channel Broadcast Automation (posts daily high-intent loan tips & links)
3. Zero External Dependencies (built on native python urllib/json)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import argparse
import random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"[!] Config file missing at {CONFIG_FILE}")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def telegram_api(method, data=None, token=None):
    """Executes a Telegram Bot API HTTP request."""
    if not token:
        cfg = load_config()
        token = cfg.get("bot_token")
    url = f"https://api.telegram.org/bot{token}/{method}"

    headers = {"Content-Type": "application/json"}
    payload = json.dumps(data).encode("utf-8") if data else None

    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[!] Telegram API error on '{method}': {e}")
        return None


def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Sends a text message with optional inline keyboard."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api("sendMessage", payload)


def handle_start(chat_id, user_first_name, cfg):
    """Sends welcoming message with interactive loan action buttons."""
    website = cfg.get("website_url", "https://novaborrow.in")
    text = (
        f"👋 *Namaste {user_first_name}! Welcome to NovaBorrow.*\n\n"
        "Need instant cash for medical emergency, rent, shopping, or bills? "
        "Hum laaye hain *100% paperless instant credit line*:\n\n"
        "⚡ *Loan Amount:* ₹5,000 se ₹50,000 tak\n"
        "⚡ *Disbursement:* 15 minute me direct bank account me\n"
        "⚡ *Eligibility:* Low CIBIL score (550+) accepted!\n"
        "⚡ *Process:* 100% Digital via Aadhaar & PAN\n\n"
        "Neeche buttons par click karke turant eligibility check karein ya direct apply karein:"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚀 Apply Online (Instant Cash)", "url": website}
            ],
            [
                {"text": "📊 Check Loan Eligibility", "callback_data": "check_eligibility"},
                {"text": "💡 Low CIBIL Tips", "callback_data": "cibil_tips"}
            ],
            [
                {"text": "❓ FAQs & Charges", "callback_data": "faqs"},
                {"text": "📞 Support", "callback_data": "support"}
            ]
        ]
    }

    send_message(chat_id, text, reply_markup=keyboard)


def handle_callback_query(query_id, chat_id, data, cfg):
    """Handles button clicks and provides immediate answers."""
    # Acknowledge callback
    telegram_api("answerCallbackQuery", {"callback_query_id": query_id})
    website = cfg.get("website_url", "https://novaborrow.in")

    if data == "check_eligibility":
        text = (
            "📋 *NovaBorrow Eligibility Criteria:*\n\n"
            "1. Age: 21+ years\n"
            "2. Indian Resident with PAN & Aadhaar\n"
            "3. Active Bank Account with UPI\n"
            "4. Minimum CIBIL: 550+ (Salary slip not required)\n\n"
            "Aapka 95% approval chance hai! Abhi 2 minute me apply karein:"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "⚡ Apply Now for ₹25,000", "url": website}]
            ]
        }
        send_message(chat_id, text, reply_markup=keyboard)

    elif data == "cibil_tips":
        text = (
            "📈 *Low CIBIL Score Par Loan Kaise Lein?*\n\n"
            "1. Ek sath 5-10 apps me apply na karein, isse CIBIL aur girta hai.\n"
            "2. Chote loans (₹10,000) le kar timely repay karein taaki score 750+ ho jaye.\n"
            "3. NovaBorrow low credit score par bhi transaction history dekhkar approve karta hai!\n\n"
            "👉 *Abhi bina CIBIL tension apply karein:*"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "👉 Apply on NovaBorrow", "url": website}]
            ]
        }
        send_message(chat_id, text, reply_markup=keyboard)

    elif data == "faqs":
        text = (
            "❓ *Frequently Asked Questions:*\n\n"
            "• *Kya koi pehle fees deni hoti hai?*\n"
            "Nahi! NovaBorrow koi upfront fee nahi leta. Complete transparent process.\n\n"
            "• *Repayment period kitna hai?*\n"
            "3 months se 12 months ke flexible EMI options.\n\n"
            "• *Paisa kab transfer hoga?*\n"
            "Approval ke 15 minute ke andar direct aapke bank account me."
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 Start Application", "url": website}]
            ]
        }
        send_message(chat_id, text, reply_markup=keyboard)

    elif data == "support":
        text = (
            "📞 *NovaBorrow Support:*\n\n"
            "Humari team aapki help ke liye 24x7 available hai.\n"
            "Website par jakar Live Chat se ya support email ke zariye sampark karein."
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "🌐 Visit Website", "url": website}]
            ]
        }
        send_message(chat_id, text, reply_markup=keyboard)


def broadcast_tip_to_channel(channel_id=None):
    """Sends an automated viral loan tip & marketing link to your channel."""
    cfg = load_config()
    target_channel = channel_id or cfg.get("channel_id")

    if not target_channel:
        print("[!] No Channel ID provided! Please specify --channel @mychannel or set 'channel_id' in config.json")
        return False

    tips = cfg.get("daily_tips", [])
    if not tips:
        print("[!] No daily tips found in config.json")
        return False

    website = cfg.get("website_url", "https://novaborrow.in")
    tip_template = random.choice(tips)
    message_text = tip_template.format(website_url=website)

    keyboard = {
        "inline_keyboard": [
            [{"text": "⚡ Apply for Instant Loan", "url": website}]
        ]
    }

    res = send_message(target_channel, message_text, reply_markup=keyboard)
    if res and res.get("ok"):
        print(f"✅ Successfully posted loan update to {target_channel}!")
        return True
    else:
        print(f"[!] Failed to post to {target_channel}. Ensure bot is an ADMIN in the channel.")
        return False


def run_interactive_listener():
    """Polls Telegram updates in real-time and handles user interactions."""
    cfg = load_config()
    token = cfg.get("bot_token")
    bot_info = telegram_api("getMe", token=token)

    if not bot_info or not bot_info.get("ok"):
        print("[!] Could not connect to Telegram Bot. Please verify your token in config.json.")
        sys.exit(1)

    bot_name = bot_info["result"]["first_name"]
    bot_user = bot_info["result"]["username"]

    print("=" * 65)
    print(f"🤖 NovaBorrow Telegram Assistant Online: @{bot_user}")
    print(f"Name: {bot_name} | Status: Listening for messages...")
    print("Users can click: https://t.me/" + bot_user)
    print("Press Ctrl+C to exit.")
    print("=" * 65)

    last_update_id = 0

    while True:
        try:
            params = {
                "offset": last_update_id + 1,
                "timeout": 20
            }
            updates = telegram_api("getUpdates", params, token=token)

            if updates and updates.get("ok"):
                for item in updates.get("result", []):
                    last_update_id = item["update_id"]

                    # Handle Callback Queries (button clicks)
                    if "callback_query" in item:
                        cb = item["callback_query"]
                        q_id = cb["id"]
                        c_id = cb["message"]["chat"]["id"]
                        data = cb.get("data", "")
                        handle_callback_query(q_id, c_id, data, cfg)
                        continue

                    # Handle Messages
                    if "message" in item:
                        msg = item["message"]
                        chat_id = msg["chat"]["id"]
                        first_name = msg.get("from", {}).get("first_name", "Friend")
                        text = msg.get("text", "").strip()

                        if text.startswith("/start"):
                            print(f"[+] User @{msg.get('from', {}).get('username', 'user')} started the bot.")
                            handle_start(chat_id, first_name, cfg)
                        else:
                            # Natural auto-reply to any loan inquiry
                            website = cfg.get("website_url", "https://novaborrow.in")
                            reply = (
                                f"Bhai aapka message mil gaya! Agar aapko urgent loan chahiye (₹5,000 se ₹50,000 tak), "
                                f"toh seedha NovaBorrow par 2 minute me apply karein bina document jhanjhat ke:\n\n"
                                f"👉 *Apply here:* {website}"
                            )
                            send_message(chat_id, reply)

            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[i] Bot stopped by user.")
            break
        except Exception as e:
            print(f"[!] Listener loop error: {e}")
            time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="NovaBorrow Automated Telegram Marketing Bot")
    parser.add_argument("--listen", action="store_true", help="Run 24x7 interactive assistant bot")
    parser.add_argument("--broadcast", action="store_true", help="Post an automated loan tip/CTA to your channel")
    parser.add_argument("--channel", type=str, default=None, help="Target channel username (e.g. @novaborrow_updates)")
    parser.add_argument("--set-channel", type=str, default=None, help="Save default channel username in config.json")
    args = parser.parse_args()

    if args.set_channel:
        cfg = load_config()
        cfg["channel_id"] = args.set_channel
        save_config(cfg)
        print(f"✔ Saved default channel: {args.set_channel}")
        return

    if args.broadcast:
        broadcast_tip_to_channel(channel_id=args.channel)
        return

    # Default action if no flags or --listen
    run_interactive_listener()


if __name__ == "__main__":
    main()
