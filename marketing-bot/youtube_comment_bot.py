#!/usr/bin/env python3
"""
YouTube Loan Marketing Automation Bot
Official YouTube Data API v3 implementation with Zero-Quota Public Search Fallback.
Finds videos targeting loan apps and posts organic marketing comments.
"""

import os
import sys
import json
import random
import time
import pickle
import argparse
import socket
import re
import shutil
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
try:
    import fcntl
except ImportError:
    fcntl = None

# Set network socket timeout to 60s
socket.setdefaulttimeout(60)

# Ensure immediate unbuffered real-time log streaming
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError:
    print("\n[ERROR] Missing required libraries! Please run:")
    print("pip install -r requirements.txt\n")
    sys.exit(1)

# YouTube OAuth Scopes (required for inserting comments)
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:
    import supabase_db
except Exception:
    supabase_db = None

CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.pickle")
CLIENT_SECRET_FILE = os.path.join(SCRIPT_DIR, "client_secret.json")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "history.json")
LEAD_HISTORY_FILE = os.path.join(SCRIPT_DIR, "lead_reply_history.json")


def load_config(config_path):
    if not os.path.exists(config_path):
        print(f"[!] Config file not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history():
    local_data = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                if fcntl:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    except Exception:
                        pass
                try:
                    local_data = json.load(f)
                finally:
                    if fcntl:
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except Exception:
                            pass
        except Exception:
            local_data = {}

    # Merge with Supabase for multi-instance cross-process/container synchronization
    if supabase_db:
        try:
            sb_videos = supabase_db.fetch_all_videos_from_supabase()
            if sb_videos:
                for vid, vdata in sb_videos.items():
                    if vid not in local_data:
                        local_data[vid] = vdata
                    else:
                        accs = list(set(local_data[vid].get("accounts", []) + vdata.get("accounts", [])))
                        local_data[vid]["accounts"] = accs
        except Exception:
            pass

    return local_data


def save_history(history, new_entry=None):
    """Process-safe history saving with lock for parallel workers + Supabase live sync."""
    if not fcntl:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    else:
        lock_path = HISTORY_FILE + ".lock"
        try:
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    disk_data = {}
                    if os.path.exists(HISTORY_FILE):
                        try:
                            with open(HISTORY_FILE, "r", encoding="utf-8") as rf:
                                disk_data = json.load(rf)
                        except Exception:
                            pass
                    disk_data.update(history)
                    temp_file = HISTORY_FILE + ".tmp"
                    with open(temp_file, "w", encoding="utf-8") as tf:
                        json.dump(disk_data, tf, indent=2, ensure_ascii=False)
                    os.replace(temp_file, HISTORY_FILE)
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

    # Persist to Supabase
    if supabase_db and new_entry:
        try:
            supabase_db.save_video_to_supabase(
                video_id=new_entry.get("video_id") or new_entry.get("id"),
                title=new_entry.get("title", ""),
                channel=new_entry.get("channel", ""),
                url=new_entry.get("url", ""),
                keyword=new_entry.get("keyword", ""),
                account=new_entry.get("account", "")
            )
        except Exception as e:
            pass


def load_lead_history():
    local_leads = {}
    if os.path.exists(LEAD_HISTORY_FILE):
        try:
            with open(LEAD_HISTORY_FILE, "r", encoding="utf-8") as f:
                if fcntl:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    except Exception:
                        pass
                try:
                    local_leads = json.load(f)
                finally:
                    if fcntl:
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except Exception:
                            pass
        except Exception:
            local_leads = {}

    # Merge with Supabase
    if supabase_db:
        try:
            sb_leads = supabase_db.fetch_all_leads_from_supabase()
            if sb_leads:
                local_leads.update(sb_leads)
        except Exception:
            pass

    return local_leads


def save_lead_history(lead_history, new_lead=None):
    """Process-safe lead history saving with lock for parallel workers + Supabase live sync."""
    if not fcntl:
        with open(LEAD_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(lead_history, f, indent=2, ensure_ascii=False)
    else:
        lock_path = LEAD_HISTORY_FILE + ".lock"
        try:
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    disk_data = {}
                    if os.path.exists(LEAD_HISTORY_FILE):
                        try:
                            with open(LEAD_HISTORY_FILE, "r", encoding="utf-8") as rf:
                                disk_data = json.load(rf)
                        except Exception:
                            pass
                    disk_data.update(lead_history)
                    temp_file = LEAD_HISTORY_FILE + ".tmp"
                    with open(temp_file, "w", encoding="utf-8") as tf:
                        json.dump(disk_data, tf, indent=2, ensure_ascii=False)
                    os.replace(temp_file, LEAD_HISTORY_FILE)
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            with open(LEAD_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(lead_history, f, indent=2, ensure_ascii=False)

    # Persist to Supabase
    if supabase_db and new_lead:
        try:
            supabase_db.save_lead_to_supabase(
                comment_id=new_lead.get("comment_id"),
                video_id=new_lead.get("video_id", ""),
                video_title=new_lead.get("video_title", ""),
                author=new_lead.get("author", ""),
                query=new_lead.get("query", ""),
                reply=new_lead.get("reply", ""),
                account=new_lead.get("account", "")
            )
        except Exception:
            pass


def backup_and_clear_history():
    if os.path.exists(HISTORY_FILE):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(SCRIPT_DIR, f"history_backup_{timestamp}.json")
        shutil.copy2(HISTORY_FILE, backup_file)
        print(f"[✔] Current history backed up to: {os.path.basename(backup_file)}")
    save_history({})
    print("[✔] History file reset successfully! You can now comment on all videos again.")


def extract_video_id(url_or_id):
    if not url_or_id:
        return None
    url_or_id = url_or_id.strip()
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id
    patterns = [
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def get_video_details(youtube, video_id):
    """Fetches details for a specific video ID."""
    try:
        response = youtube.videos().list(part="snippet", id=video_id).execute()
        items = response.get("items", [])
        if items:
            snippet = items[0]["snippet"]
            return {
                "id": video_id,
                "title": snippet.get("title", f"Video {video_id}"),
                "channel": snippet.get("channelTitle", "Unknown Channel"),
                "url": f"https://www.youtube.com/watch?v={video_id}"
            }
    except Exception as e:
        print(f"[!] Could not fetch video details for {video_id}: {e}")
    return {
        "id": video_id,
        "title": f"Video {video_id}",
        "channel": "YouTube",
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }


def get_token_file(client_secret_path):
    """Returns a unique token.pickle path for each client_secret file or project."""
    base = os.path.basename(client_secret_path)
    name, _ = os.path.splitext(base)
    if name == "client_secret":
        return os.path.join(SCRIPT_DIR, "token.pickle")

    # Use project_id if available for a clean token filename
    try:
        with open(client_secret_path, "r", encoding="utf-8") as f:
            s_data = json.load(f)
            proj_id = (
                s_data.get("installed", {}).get("project_id")
                or s_data.get("web", {}).get("project_id")
            )
            if proj_id:
                return os.path.join(SCRIPT_DIR, f"token_{proj_id}.pickle")
    except Exception:
        pass

    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    return os.path.join(SCRIPT_DIR, f"token_{clean_name[:30]}.pickle")


def get_client_id_from_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return (
                data.get("installed", {}).get("client_id")
                or data.get("web", {}).get("client_id")
            )
    except Exception:
        return None


def find_all_client_secrets(custom_secret=None):
    """Finds all available client_secret JSON files in marketing-bot and jsons/ folder."""
    if custom_secret and os.path.exists(custom_secret):
        return [custom_secret]

    candidates = []
    # Primary default in root
    if os.path.exists(CLIENT_SECRET_FILE):
        candidates.append(CLIENT_SECRET_FILE)

    # Scan root script directory
    for fname in sorted(os.listdir(SCRIPT_DIR)):
        if fname.startswith("client_secret") and fname.endswith(".json") and not fname.endswith(".example.json"):
            full_path = os.path.join(SCRIPT_DIR, fname)
            if full_path not in candidates and os.path.isfile(full_path):
                candidates.append(full_path)

    # Recursively scan jsons folder and all subfolders (e.g. jsons/pano/)
    jsons_dir = os.path.join(SCRIPT_DIR, "jsons")
    if os.path.isdir(jsons_dir):
        for root, _, files in os.walk(jsons_dir):
            for fname in sorted(files):
                if fname.endswith(".json") and not fname.endswith(".example.json"):
                    full_path = os.path.join(root, fname)
                    if full_path not in candidates and os.path.isfile(full_path):
                        candidates.append(full_path)

    # Deduplicate by client_id so same project isn't added twice
    unique_secrets = []
    seen_client_ids = set()
    for path in candidates:
        cid = get_client_id_from_file(path)
        if cid:
            if cid not in seen_client_ids:
                seen_client_ids.add(cid)
                unique_secrets.append(path)
        else:
            if path not in unique_secrets:
                unique_secrets.append(path)

    return unique_secrets


def get_authenticated_service(client_secret_path=CLIENT_SECRET_FILE, token_path=None):
    """Authenticates the user using OAuth 2.0 and returns the YouTube service."""
    if token_path is None:
        token_path = get_token_file(client_secret_path)

    credentials = None

    # Auto-detect if client_secret changed and invalidate stale token
    if os.path.exists(client_secret_path) and os.path.exists(token_path):
        try:
            with open(client_secret_path, "r", encoding="utf-8") as f:
                secret_data = json.load(f)
                current_client_id = (
                    secret_data.get("installed", {}).get("client_id")
                    or secret_data.get("web", {}).get("client_id")
                )
            with open(token_path, "rb") as token:
                cached_creds = pickle.load(token)
                if hasattr(cached_creds, "client_id") and cached_creds.client_id and current_client_id:
                    if cached_creds.client_id != current_client_id:
                        print(f"\n[i] Naya {os.path.basename(client_secret_path)} detect hua! Re-authenticating...")
                        os.remove(token_path)
                        credentials = None
                    else:
                        credentials = cached_creds
                else:
                    credentials = cached_creds
        except Exception:
            credentials = None
    elif os.path.exists(token_path):
        with open(token_path, "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as e:
                print(f"[!] Error refreshing credentials ({os.path.basename(token_path)}): {e}")
                credentials = None

        if not credentials:
            if not os.path.exists(client_secret_path):
                print("\n" + "=" * 65)
                print(f"[!] '{os.path.basename(client_secret_path)}' file is missing!")
                print(f"Please download your OAuth 2.0 Client credentials from Google Cloud Console")
                print(f"and place it as: {client_secret_path}")
                print("=" * 65 + "\n")
                sys.exit(1)

            print(f"\n🔐 One-time authentication needed for: {os.path.basename(client_secret_path)}")
            print("Opening browser for OAuth authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            credentials = flow.run_local_server(port=0)

        with open(token_path, "wb") as token:
            pickle.dump(credentials, token)

    return build("youtube", "v3", credentials=credentials)


class YouTubeAccountManager:
    """
    Manages multiple YouTube API/OAuth projects.
    Supports:
    1. Posting unique comments from ALL accounts on each video.
    2. Tracking quota exhaustion per account independently.
    """
    def __init__(self, secret_paths):
        self.accounts = []
        for idx, path in enumerate(secret_paths, 1):
            proj_id = "unknown"
            try:
                with open(path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    proj_id = (
                        s_data.get("installed", {}).get("project_id")
                        or s_data.get("web", {}).get("project_id")
                        or "unknown"
                    )
            except Exception:
                pass
            self.accounts.append({
                "index": idx,
                "secret_path": path,
                "token_path": get_token_file(path),
                "project_id": proj_id,
                "filename": os.path.basename(path),
                "label": f"Account #{idx} [Project: '{proj_id}']",
                "service": None,
                "exhausted": False
            })

    @property
    def total_accounts(self):
        return len(self.accounts)

    def get_service_for(self, acc):
        if acc.get("service") is not None:
            return acc["service"]
        service = get_authenticated_service(acc["secret_path"], acc["token_path"])
        acc["service"] = service
        return service

    def mark_exhausted(self, acc):
        acc["exhausted"] = True
        print(f"\n   [⚠️ QUOTA EXHAUSTED] {acc['label']} reached daily comment posting limit.")
        active = self.get_active_accounts()
        if active:
            print(f"   ℹ️ Remaining active accounts for subsequent videos: {len(active)} ({', '.join(a['label'] for a in active)})")
        else:
            print(f"   ⚠️ All {self.total_accounts} accounts have reached their daily commenting quota!")

    def get_active_accounts(self):
        return [acc for acc in self.accounts if not acc.get("exhausted", False)]

    def has_active_accounts(self):
        return len(self.get_active_accounts()) > 0


def generate_dynamic_comment(config, exclude=None):
    """Generates 100% natural, conversational user testimonial comment, ensuring unique comments across accounts."""
    exclude = set(exclude or [])
    natural_comments = config.get("natural_comments", [])
    available_templates = [t for t in natural_comments if t not in exclude]
    if not available_templates:
        available_templates = natural_comments

    if available_templates:
        template = random.choice(available_templates)
        placeholders = config.get("placeholders", {})
        amounts = placeholders.get("amounts", ["20k", "25k", "30k", "35k"])
        timeframes = placeholders.get("timeframes", ["10-15 minute me", "aadhi ghante me", "turant"])

        amount = random.choice(amounts)
        timeframe = random.choice(timeframes)

        try:
            return template.format(amount=amount, timeframe=timeframe)
        except Exception:
            return template

    spintax = config.get("comment_spintax", {})
    greetings = spintax.get("greetings", ["Bhai sahi video hai."])
    propositions = spintax.get("propositions", ["Maine NovaBorrow use kiya tha 30k mil gaye the."])
    return f"{random.choice(greetings)} {random.choice(propositions)}"


def is_lead_comment(comment_text, author_name, config):
    """
    Detects if a YouTube comment is from an emergency loan seeker.
    Filters out bots, promotional comments, and our own accounts.
    """
    if not comment_text or len(comment_text.strip()) < 5:
        return False, []

    text_lower = comment_text.lower()
    lead_cfg = config.get("lead_seeker_settings", {})

    # Exclude our own or promotional links/codes
    exclude_list = lead_cfg.get("exclude_phrases", ["novaborrow", "telegram", "whatsapp", "promo", "join"])
    for ex in exclude_list:
        if ex in text_lower:
            return False, []

    # Filter out generic compliments (e.g. "helpful video", "great information")
    if "helpful" in text_lower or "helpfull" in text_lower:
        strong_loan_signals = ["chahiye", "loan", "cibil", "reject", "urgent", "emergency", "pareshan", "paisa", "rupaye", "milega", "batao"]
        if not any(sig in text_lower for sig in strong_loan_signals):
            return False, []

    # Ignore DSA / financial sales comments
    if "as a dsa" in text_lower or "loan agent" in text_lower:
        return False, []

    lead_keywords = lead_cfg.get("lead_keywords", [
        "chahiye", "urgent", "emergency", "pareshan", "reject", "cibil",
        "bata do", "batao", "kaise milega", "kahan milega", "kaise le",
        "konsa app", "help", "need loan", "salary slip", "income proof"
    ])

    matched = []
    for kw in lead_keywords:
        if kw == "help":
            # Match standalone 'help' but not 'helpful'
            if re.search(r'\bhelp\b', text_lower) and not re.search(r'\bhelp(ful|full)\b', text_lower):
                matched.append("help")
        elif kw in text_lower:
            matched.append(kw)

    if matched:
        return True, matched
    return False, []


def generate_lead_reply(config, exclude=None):
    """Generates empathetic, natural conversational reply addressing the loan seeker."""
    exclude = set(exclude or [])
    lead_cfg = config.get("lead_seeker_settings", {})
    templates = lead_cfg.get("lead_reply_templates", [])
    if not templates:
        return generate_dynamic_comment(config, exclude=exclude)

    available = [t for t in templates if t not in exclude]
    if not available:
        available = templates

    template = random.choice(available)
    placeholders = config.get("placeholders", {})
    amounts = placeholders.get("amounts", ["15k", "20k", "25k", "30k"])
    timeframes = placeholders.get("timeframes", ["10-15 minute me", "aadhi ghante me", "turant"])

    amount = random.choice(amounts)
    timeframe = random.choice(timeframes)

    try:
        return template.format(amount=amount, timeframe=timeframe)
    except Exception:
        return template


def search_youtube_public(keyword, sort="relevance"):
    """
    Public YouTube search scraper (Consumes 0 API Quota units).
    Bypasses YouTube Data API search quota limits completely.
    """
    try:
        encoded_kw = urllib.parse.quote_plus(keyword)
        url = f"https://www.youtube.com/results?search_query={encoded_kw}"
        if sort == "date":
            url += "&sp=CAI%253D"
        elif sort == "viewCount":
            url += "&sp=CAM%253D"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "hi,en;q=0.9"
            }
        )
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")

        videos = []
        seen_ids = set()

        m = re.search(r'ytInitialData\s*=\s*({.+?});</script>', html)
        if m:
            data = json.loads(m.group(1))
            contents = (
                data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            for section in contents:
                items = section.get("itemSectionRenderer", {}).get("contents", [])
                for item in items:
                    v = item.get("videoRenderer")
                    if v and v.get("videoId"):
                        vid = v.get("videoId")
                        if vid not in seen_ids:
                            seen_ids.add(vid)
                            title = v.get("title", {}).get("runs", [{}])[0].get("text", "")
                            channel = v.get("ownerText", {}).get("runs", [{}])[0].get("text", "YouTube Channel")
                            videos.append({
                                "id": vid,
                                "title": title,
                                "channel": channel,
                                "url": f"https://www.youtube.com/watch?v={vid}"
                            })

        if not videos:
            raw_ids = list(dict.fromkeys(re.findall(r'\"videoId\":\"([a-zA-Z0-9_-]{11})\"', html)))
            for vid in raw_ids[:25]:
                if vid not in seen_ids:
                    seen_ids.add(vid)
                    videos.append({
                        "id": vid,
                        "title": f"Loan Video ({vid})",
                        "channel": "YouTube Creator",
                        "url": f"https://www.youtube.com/watch?v={vid}"
                    })

        return videos
    except Exception as e:
        print(f"   [!] Public search error: {e}")
        return []


def search_target_videos(youtube, keyword, days_back=60, max_results=50, region_code="IN",
                         order="relevance", relevance_language="hi", max_pages=2, force_public=False):
    """
    Searches for videos matching loan keywords.
    Automatically falls back to Zero-Quota Public Search if Google API quota is exhausted.
    """
    if force_public or youtube is None:
        return "PUBLIC_SUCCESS", search_youtube_public(keyword, sort=order)

    published_after = None
    if days_back and days_back > 0:
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat()

    videos = []
    seen_ids = set()
    page_token = None

    for page in range(max_pages):
        params = {
            "part": "id,snippet",
            "q": keyword,
            "type": "video",
            "order": order,
            "regionCode": region_code,
            "maxResults": min(max_results, 50),
        }
        if published_after:
            params["publishedAfter"] = published_after
        if relevance_language:
            params["relevanceLanguage"] = relevance_language
        if page_token:
            params["pageToken"] = page_token

        try:
            response = youtube.search().list(**params).execute()
            items = response.get("items", [])
            for item in items:
                video_id = item["id"].get("videoId")
                if video_id and video_id not in seen_ids:
                    seen_ids.add(video_id)
                    videos.append({
                        "id": video_id,
                        "title": item["snippet"].get("title", ""),
                        "channel": item["snippet"].get("channelTitle", ""),
                        "published_at": item["snippet"].get("publishedAt", ""),
                        "url": f"https://www.youtube.com/watch?v={video_id}"
                    })

            page_token = response.get("nextPageToken")
            if not page_token or len(items) == 0:
                break
        except HttpError as e:
            if "quotaExceeded" in str(e) or "rateLimitExceeded" in str(e):
                print(f"   [⚡ AUTO-SWITCH] YouTube API Search Quota is full! Switching seamlessly to Zero-Quota Public Search...")
                public_vids = search_youtube_public(keyword, sort=order)
                return "QUOTA_FALLBACK", public_vids
            print(f"[!] YouTube Search API error for keyword '{keyword}' (order={order}): {e}")
            public_vids = search_youtube_public(keyword, sort=order)
            return "ERROR_FALLBACK", public_vids
        except Exception as e:
            print(f"[!] Network error during search for '{keyword}': {e}. Using public search...")
            return "ERROR_FALLBACK", search_youtube_public(keyword, sort=order)

    return "API_SUCCESS", videos


def post_comment(youtube, video_id, comment_text, dry_run=False):
    """Inserts a top-level comment to a YouTube video with retry and error handling."""
    if dry_run:
        print(f"[DRY-RUN] Would post to video {video_id}:")
        print("-" * 50)
        print(comment_text)
        print("-" * 50)
        return True

    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {
                "snippet": {
                    "textOriginal": comment_text
                }
            }
        }
    }

    try:
        youtube.commentThreads().insert(
            part="snippet",
            body=body
        ).execute()
        return True
    except HttpError as e:
        if "commentsDisabled" in str(e) or "forbidden" in str(e):
            print(f"   [!] Is video par creator ne comments band (disabled) kar rakhe hain. Skipping...")
            return False
        elif "quotaExceeded" in str(e):
            print(f"\n[⚠️ QUOTA REACHED] YouTube API Comment Posting quota limit reach ho chuki hai.")
            return "QUOTA_EXCEEDED"
        else:
            print(f"   [!] YouTube API Error on video {video_id}: {e}")
            return False
    except Exception as e:
        print(f"   [!] Network/Connection issue ({type(e).__name__}): {e}. Skipping video safely...")
        return False


def post_reply(youtube, parent_comment_id, reply_text, dry_run=False):
    """Inserts a reply to an existing YouTube comment thread."""
    if dry_run:
        print(f"      [DRY-RUN] Simulated reply to comment {parent_comment_id}:")
        print(f"      \"{reply_text}\"")
        return True

    body = {
        "snippet": {
            "parentId": parent_comment_id,
            "textOriginal": reply_text
        }
    }

    try:
        youtube.comments().insert(
            part="snippet",
            body=body
        ).execute()
        return True
    except HttpError as e:
        err_str = str(e)
        if "commentsDisabled" in err_str or "forbidden" in err_str:
            print(f"   [!] Replies are disabled for this comment. Skipping...")
            return False
        elif "quotaExceeded" in err_str:
            print(f"\n[⚠️ QUOTA REACHED] YouTube API quota limit reached for this account.")
            return "QUOTA_EXCEEDED"
        else:
            print(f"   [!] YouTube API Error while replying: {e}")
            return False
    except Exception as e:
        print(f"   [!] Network issue while replying: {e}")
        return False


def get_video_comment_threads(youtube, video_id, max_results=50):
    """Fetches latest comments from a YouTube video to scan for leads (1 quota unit)."""
    if not youtube:
        return []
    try:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100),
            order="time",
            textFormat="plainText"
        ).execute()
        return response.get("items", [])
    except HttpError as e:
        if "commentsDisabled" in str(e):
            return []
        print(f"   [!] Could not fetch comments for video {video_id}: {e}")
        return []
    except Exception as e:
        return []


def scan_and_reply_leads_on_video(youtube_acc_mgr, v_info, config, args, lead_history, max_leads=3):
    """
    Scans a video's comments for loan seekers and replies directly using rotating accounts.
    Returns number of replies sent.
    """
    vid_id = v_info["id"]
    v_title = v_info["title"]
    active_accs = youtube_acc_mgr.get_active_accounts()
    if not active_accs:
        return 0

    scan_svc = youtube_acc_mgr.get_service_for(active_accs[0]) if active_accs else None
    threads = get_video_comment_threads(scan_svc, vid_id, max_results=50)
    if not threads:
        return 0

    replies_done = 0
    used_replies = []

    for item in threads:
        if replies_done >= max_leads or not youtube_acc_mgr.has_active_accounts():
            break

        top_snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        comment_id = item.get("snippet", {}).get("topLevelComment", {}).get("id") or item.get("id")
        author_name = top_snippet.get("authorDisplayName", "User")
        comment_text = top_snippet.get("textOriginal") or top_snippet.get("textDisplay", "")

        if not comment_id or not comment_text:
            continue

        if comment_id in lead_history and not args.ignore_history:
            continue

        is_lead, matched_kws = is_lead_comment(comment_text, author_name, config)
        if not is_lead:
            continue

        active_accs = youtube_acc_mgr.get_active_accounts()
        if not active_accs:
            break

        # Pick account in rotation
        chosen_acc = active_accs[replies_done % len(active_accs)]

        reply_text = generate_lead_reply(config, exclude=used_replies)
        used_replies.append(reply_text)

        print(f"\n   🎯 [LOAN SEEKER LEAD FOUND on this video]")
        print(f"      👤 Seeker: {author_name}")
        print(f"      💬 Query: \"{comment_text.strip().replace(chr(10), ' ')[:85]}...\"")
        print(f"      ⚡ Intent: {', '.join(matched_kws)}")
        print(f"      👉 [{chosen_acc['label']}] Replying to user:")
        print(f"         \"{reply_text}\"")

        if args.dry_run:
            replies_done += 1
            lead_history[comment_id] = {
                "author": author_name,
                "video_id": vid_id,
                "video_title": v_title,
                "query": comment_text.strip(),
                "reply": reply_text,
                "account": chosen_acc["project_id"],
                "timestamp": datetime.now().isoformat()
            }
            print(f"         [DRY-RUN] Simulated lead reply posted!")
        else:
            svc = youtube_acc_mgr.get_service_for(chosen_acc)
            res = post_reply(svc, comment_id, reply_text, dry_run=False)

            if res == "QUOTA_EXCEEDED":
                youtube_acc_mgr.mark_exhausted(chosen_acc)
                continue
            elif res is True:
                replies_done += 1
                lead_history[comment_id] = {
                    "author": author_name,
                    "video_id": vid_id,
                    "video_title": v_title,
                    "query": comment_text.strip(),
                    "reply": reply_text,
                    "account": chosen_acc["project_id"],
                    "timestamp": datetime.now().isoformat()
                }
                new_lead_entry = {
                    "comment_id": comment_id,
                    "video_id": vid_id,
                    "video_title": v_title,
                    "author": author_name,
                    "query": comment_text.strip(),
                    "reply": reply_text,
                    "account": chosen_acc["project_id"]
                }
                save_lead_history(lead_history, new_lead=new_lead_entry)
                print(f"         ✅ [{chosen_acc['label']}] Reply successfully sent to user! (Saved to Supabase)")

                if replies_done < max_leads and youtube_acc_mgr.has_active_accounts():
                    rep_delay = random.randint(15, 30)
                    print(f"         ⏳ Safety delay: Waiting {rep_delay}s before replying to next lead...")
                    time.sleep(rep_delay)

    return replies_done


def run_lead_seeker_bot(account_mgr, config, args, max_comments, min_delay, max_delay,
                        keywords, days_back, max_results, region_code, orders_to_try,
                        max_pages, using_public_search):
    """
    Category 1 Lead Seeker Engine:
    Scans YouTube comments on finance & loan videos.
    Identifies high-intent users asking for emergency loans/low cibil/help.
    Auto-replies directly to them using rotating accounts with empathetic NovaBorrow recommendations.
    """
    lead_history = load_lead_history()
    search_cfg = config.get("search_settings", {})

    print("\n" + "=" * 65)
    print("  🎯 CATEGORY 1: INSTANT TRAFFIC - LOAN SEEKER LEAD REPLY BOT 🎯")
    print("=" * 65)
    print(f"Mode: {'[DRY RUN - SIMULATION ONLY]' if args.dry_run else '[LIVE POSTING]'}")
    print("Strategy: Scan comments of finance & loan videos for users needing urgent cash")
    print("Action: Auto-reply directly to their comment with empathetic NovaBorrow recommendation")
    print(f"Target Max Replies: {max_comments}")
    print(f"Safety delay range: 20s - 45s between replies")
    print(f"Leads already replied in history: {len(lead_history)}")
    print(f"Connected API Accounts for rotation: {account_mgr.total_accounts}")
    for idx, acc in enumerate(account_mgr.accounts, 1):
        print(f"   • Account #{idx}: {acc['label']}")
    print("=" * 65 + "\n")

    replied_count = 0
    used_replies = []
    account_cycle_idx = 0

    def scan_and_reply_video(v_info):
        nonlocal replied_count, account_cycle_idx
        vid_id = v_info["id"]
        v_title = v_info["title"]
        v_url = v_info.get("url", f"https://www.youtube.com/watch?v={vid_id}")

        active_accs = account_mgr.get_active_accounts()
        if not active_accs:
            return 0

        # Scan comments using first active service (costs only 1 quota unit)
        scan_svc = account_mgr.get_service_for(active_accs[0]) if active_accs else None
        threads = get_video_comment_threads(scan_svc, vid_id, max_results=50)

        if not threads:
            return 0

        leads_found_this_video = 0
        for item in threads:
            if replied_count >= max_comments or not account_mgr.has_active_accounts():
                break

            top_snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            comment_id = item.get("snippet", {}).get("topLevelComment", {}).get("id") or item.get("id")
            author_name = top_snippet.get("authorDisplayName", "User")
            comment_text = top_snippet.get("textOriginal") or top_snippet.get("textDisplay", "")

            if not comment_id or not comment_text:
                continue

            # Don't reply if already replied previously
            if comment_id in lead_history and not args.ignore_history:
                continue

            is_lead, matched_kws = is_lead_comment(comment_text, author_name, config)
            if not is_lead:
                continue

            active_accs = account_mgr.get_active_accounts()
            if not active_accs:
                break

            # Rotate through accounts for distinct organic replies
            chosen_acc = active_accs[account_cycle_idx % len(active_accs)]
            account_cycle_idx += 1

            reply_text = generate_lead_reply(config, exclude=used_replies)
            used_replies.append(reply_text)
            if len(used_replies) > 10:
                used_replies.pop(0)

            print(f"\n🎯 [LEAD FOUND on: '{v_title[:55]}...']")
            print(f"   👤 Seeker: {author_name}")
            print(f"   💬 Query: \"{comment_text.strip().replace(chr(10), ' ')[:90]}...\"")
            print(f"   ⚡ Matched Intent: {', '.join(matched_kws)}")
            print(f"   👉 [{chosen_acc['label']}] Replying:")
            print(f"      \"{reply_text}\"")

            if args.dry_run:
                replied_count += 1
                leads_found_this_video += 1
                lead_history[comment_id] = {
                    "author": author_name,
                    "video_id": vid_id,
                    "video_title": v_title,
                    "query": comment_text.strip(),
                    "reply": reply_text,
                    "account": chosen_acc["project_id"],
                    "timestamp": datetime.now().isoformat()
                }
                print(f"      [DRY-RUN] Simulated reply posted! Progress: [{replied_count}/{max_comments}]")
            else:
                svc = account_mgr.get_service_for(chosen_acc)
                res = post_reply(svc, comment_id, reply_text, dry_run=False)

                if res == "QUOTA_EXCEEDED":
                    account_mgr.mark_exhausted(chosen_acc)
                    continue
                elif res is True:
                    replied_count += 1
                    leads_found_this_video += 1
                    lead_history[comment_id] = {
                        "author": author_name,
                        "video_id": vid_id,
                        "video_title": v_title,
                        "query": comment_text.strip(),
                        "reply": reply_text,
                        "account": chosen_acc["project_id"],
                        "timestamp": datetime.now().isoformat()
                    }
                    new_lead_entry = {
                        "comment_id": comment_id,
                        "video_id": vid_id,
                        "video_title": v_title,
                        "author": author_name,
                        "query": comment_text.strip(),
                        "reply": reply_text,
                        "account": chosen_acc["project_id"]
                    }
                    save_lead_history(lead_history, new_lead=new_lead_entry)
                    print(f"      ✅ [{chosen_acc['label']}] Reply successfully sent to user! (Saved to Supabase) Progress: [{replied_count}/{max_comments}]")

                    if replied_count < max_comments and account_mgr.has_active_accounts():
                        rep_delay = random.randint(20, 45)
                        print(f"      ⏳ Safety delay: Waiting {rep_delay}s before next reply...")
                        time.sleep(rep_delay)

        return leads_found_this_video

    # Check if direct video specified
    direct_target = args.url or args.video_id
    if direct_target:
        v_id = extract_video_id(direct_target)
        print(f"🎯 Scanning specific target video for leads: {v_id}")
        active_list = account_mgr.get_active_accounts()
        first_svc = account_mgr.get_service_for(active_list[0]) if active_list else None
        video_info = get_video_details(first_svc, v_id) if first_svc else {"id": v_id, "title": f"Video {v_id}", "channel": "YouTube", "url": direct_target}
        scan_and_reply_video(video_info)
        print("\n" + "=" * 65)
        print(f"🎉 Lead Bot finished! Total leads replied: {replied_count}")
        print("=" * 65 + "\n")
        return

    # Automated search across loan keywords
    shuffled_keywords = list(keywords)
    random.shuffle(shuffled_keywords)

    for kw in shuffled_keywords:
        if replied_count >= max_comments or not account_mgr.has_active_accounts():
            break

        for current_order in orders_to_try:
            if replied_count >= max_comments or not account_mgr.has_active_accounts():
                break

            search_mode_label = "Zero-Quota Public" if using_public_search else "YouTube API"
            print(f"\n🔍 Searching loan videos to scan: '{kw}' [mode: {search_mode_label}, sort: {current_order}]...")

            active_list = account_mgr.get_active_accounts()
            search_svc = account_mgr.get_service_for(active_list[0]) if (active_list and not using_public_search) else None

            status, videos = search_target_videos(
                search_svc,
                keyword=kw,
                days_back=days_back,
                max_results=max_results,
                region_code=region_code,
                order=current_order,
                relevance_language="hi",
                max_pages=max_pages,
                force_public=using_public_search
            )

            if status == "QUOTA_FALLBACK":
                using_public_search = True

            print(f"   Found {len(videos)} videos. Scanning comments for loan seekers...")

            for video in videos:
                if replied_count >= max_comments or not account_mgr.has_active_accounts():
                    break

                negative_keywords = search_cfg.get("negative_keywords", [])
                title_lower = video["title"].lower()
                if any(neg.lower() in title_lower for neg in negative_keywords):
                    continue

                leads_found = scan_and_reply_video(video)
                if leads_found > 0 and replied_count < max_comments and account_mgr.has_active_accounts():
                    v_delay = random.randint(min_delay, max_delay)
                    print(f"   ⏳ Finished video scan ({leads_found} leads replied). Sleeping {v_delay}s before next video...")
                    time.sleep(v_delay)

    print("\n" + "=" * 65)
    print(f"🎉 Category 1 Lead Bot completed! Total leads replied: {replied_count}")
    print(f"💾 Replied leads logged to: {os.path.basename(LEAD_HISTORY_FILE)}")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="YouTube Automated Loan Marketing Bot")
    parser.add_argument("--dry-run", action="store_true", help="Run in test mode without posting comments")
    parser.add_argument("--limit", type=int, default=None, help="Override maximum comments for this run")
    parser.add_argument("--keyword", type=str, default=None, help="Specific search keyword to target")
    parser.add_argument("--order", type=str, default=None, choices=["relevance", "viewCount", "date", "all"],
                        help="Sort order: relevance, viewCount, date, or all (cycles through orders)")
    parser.add_argument("--days", type=int, default=None, help="Days back to search (e.g. 60, 90). 0 for all time.")
    parser.add_argument("--pages", type=int, default=None, help="Max search result pages to fetch per keyword (default 2)")
    parser.add_argument("--url", type=str, default=None, help="Direct YouTube video URL to comment on")
    parser.add_argument("--video-id", type=str, default=None, help="Direct YouTube video ID to comment on")
    parser.add_argument("--public-search", action="store_true", help="Use zero-quota public YouTube search instead of API search")
    parser.add_argument("--ignore-history", action="store_true", help="Post comment even if video is in history.json")
    parser.add_argument("--clear-history", action="store_true", help="Backup and reset history.json to allow commenting on all videos again")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm prompt for --clear-history")
    parser.add_argument("--secret", type=str, default=CLIENT_SECRET_FILE, help="Path to client_secret.json (to use another Google Cloud project)")
    parser.add_argument("--secrets", type=str, default=None, help="Comma-separated list of client_secret JSON paths to use (allows custom selection of accounts)")
    parser.add_argument("--config", type=str, default=CONFIG_FILE, help="Path to config.json")
    parser.add_argument("--history", action="store_true", help="Print past commented videos and exit")
    parser.add_argument("--reply-leads", "--lead-bot", action="store_true",
                        help="Category 1 Mode: Scan video comments & auto-reply directly to loan seekers (Highest conversion)")
    parser.add_argument("--hybrid", "--combo", action="store_true",
                        help="🚀 Hybrid Mode: Post 3 comments from 3 accounts on each video AND auto-reply to loan seekers on that video")
    parser.add_argument("--instance-id", type=str, default="Worker-1",
                        help="Worker/Instance identifier for parallel execution (e.g. Instance-1, Instance-2)")
    args = parser.parse_args()

    if args.clear_history:
        if args.yes:
            backup_and_clear_history()
        else:
            try:
                confirm = input("Are you sure you want to backup and clear history.json? (y/n): ").strip().lower()
                if confirm == 'y':
                    backup_and_clear_history()
                else:
                    print("[i] Operation cancelled.")
            except (EOFError, KeyboardInterrupt):
                print("[i] Cancelled.")
        return

    history = load_history()
    lead_history = load_lead_history()

    if args.history:
        print(f"\n[INFO] Total commented videos in history: {len(history)}")
        for vid, data in history.items():
            print(f"- [{data.get('timestamp')}] {data.get('title')} ({vid})")
        return

    config = load_config(args.config)
    search_cfg = config.get("search_settings", {})
    limits_cfg = config.get("bot_limits", {})

    max_comments = args.limit or limits_cfg.get("max_comments_per_run", 10)
    min_delay = limits_cfg.get("min_delay_seconds", 30)
    max_delay = limits_cfg.get("max_delay_seconds", 60)
    days_back = args.days if args.days is not None else search_cfg.get("days_back", 60)
    max_pages = args.pages or search_cfg.get("max_pages_per_keyword", 2)
    max_results = search_cfg.get("max_results_per_search", 50)
    region_code = search_cfg.get("region_code", "IN")
    relevance_language = search_cfg.get("relevance_language", "hi")

    order_arg = args.order or search_cfg.get("order", "all")
    if order_arg == "all":
        orders_to_try = search_cfg.get("orders", ["relevance", "viewCount", "date"])
    else:
        orders_to_try = [order_arg]

    keywords = [args.keyword] if args.keyword else search_cfg.get("keywords", ["best loan app"])

    print("=" * 65)
    print(f"      🚀 NOVA BORROW YOUTUBE AUTOMATION [{args.instance_id.upper()}] 🚀")
    print("=" * 65)
    print(f"Mode: {'[DRY RUN - SIMULATION ONLY]' if args.dry_run else '[LIVE POSTING]'}")
    print(f"Target Max Comments: {max_comments}")
    print(f"Search Window: Last {days_back} days" if days_back > 0 else "Search Window: All-time")
    print(f"Search Orders: {', '.join(orders_to_try)}")
    print(f"Keywords pool: {len(keywords)} terms")
    print(f"Safety delay range: {min_delay}s - {max_delay}s between comments")
    print(f"Videos already in history: {len(history)}")

    # Discover and setup API accounts
    if args.secrets:
        secret_paths = [p.strip() for p in args.secrets.split(",") if p.strip() and os.path.exists(p.strip())]
    elif args.secret != CLIENT_SECRET_FILE and os.path.exists(args.secret):
        secret_paths = [args.secret]
    else:
        secret_paths = find_all_client_secrets()

    if not secret_paths:
        print("\n" + "=" * 65)
        print(f"[!] No client_secret JSON file found in {SCRIPT_DIR}!")
        print("Please place client_secret.json (or client_secret_2.json, etc.)")
        print("=" * 65 + "\n")
        sys.exit(1)

    account_mgr = YouTubeAccountManager(secret_paths)

    print(f"Connected API Projects: {account_mgr.total_accounts}")
    for idx, acc in enumerate(account_mgr.accounts, 1):
        print(f"   • Account #{idx}: {acc['label']}")
    if args.hybrid:
        print("Multi-Account Mode: [🚀 HYBRID COMBO - 3 ACCOUNTS COMMENT + DIRECT LOAN SEEKER AUTO-REPLY]")
    else:
        print("Multi-Account Mode: [ALL ACCOUNTS PER VIDEO - UNIQUE COMMENTS]")
    if args.ignore_history:
        print("[!] --ignore-history is ACTIVE: Past history will not block commenting.")
    if args.public_search:
        print("[⚡] --public-search is ACTIVE: Zero-Quota Search Mode enabled.")
    print("=" * 65)

    # Initialize YouTube Clients
    if not args.dry_run:
        print("\n[+] Initializing and verifying all YouTube API accounts...")
        ready_count = 0
        for acc in account_mgr.accounts:
            try:
                svc = account_mgr.get_service_for(acc)
                if svc:
                    ready_count += 1
                    print(f"   [✔] Ready: {acc['label']}")
            except Exception as e:
                print(f"   [!] Could not authenticate {acc['label']}: {e}")
                acc["exhausted"] = True

        if not account_mgr.has_active_accounts():
            print("[ERROR] None of the YouTube API accounts could be authenticated.")
            sys.exit(1)
        print(f"[✔] Total {ready_count}/{account_mgr.total_accounts} accounts ready to post!")

    posted_count = 0
    skipped_history_count = 0
    using_public_search = args.public_search

    def post_multi_account_to_video(v_info, kw_label=None, order_label=None):
        nonlocal posted_count
        vid_id = v_info["id"]
        v_title = v_info["title"]
        v_channel = v_info["channel"]
        v_url = v_info["url"]

        # Determine which active accounts have not yet posted on this video
        past_record = history.get(vid_id, {})
        already_posted_accs = past_record.get("accounts", []) if isinstance(past_record, dict) else []

        active_accs = [
            a for a in account_mgr.get_active_accounts()
            if args.ignore_history or a["project_id"] not in already_posted_accs
        ]

        if not active_accs:
            return 0

        print(f"\n🎯 Target Video: {v_title}")
        print(f"   Channel: {v_channel} | URL: {v_url}")
        print(f"   👥 Posting {len(active_accs)} distinct comments using active accounts...")

        used_comments_for_video = []
        video_success_count = 0

        for i, acc in enumerate(active_accs):
            if posted_count >= max_comments or not account_mgr.has_active_accounts():
                break

            comment_text = generate_dynamic_comment(config, exclude=used_comments_for_video)

            print(f"\n   👉 [{acc['label']}] Preparing unique comment:")
            print(f"      \"{comment_text}\"")

            if args.dry_run:
                posted_count += 1
                video_success_count += 1
                used_comments_for_video.append(comment_text)
                print(f"      [DRY-RUN] Simulated posted! Progress: [{posted_count}/{max_comments}]")
            else:
                svc = account_mgr.get_service_for(acc)
                result = post_comment(svc, vid_id, comment_text, dry_run=False)

                if result == "QUOTA_EXCEEDED":
                    account_mgr.mark_exhausted(acc)
                    continue
                elif result is True:
                    posted_count += 1
                    video_success_count += 1
                    used_comments_for_video.append(comment_text)

                    # Update history
                    if vid_id not in history:
                        history[vid_id] = {
                            "title": v_title,
                            "channel": v_channel,
                            "url": v_url,
                            "timestamp": datetime.now().isoformat(),
                            "keyword": kw_label or "direct_target",
                            "accounts": []
                        }
                    if "accounts" not in history[vid_id]:
                        history[vid_id]["accounts"] = []
                    if acc["project_id"] not in history[vid_id]["accounts"]:
                        history[vid_id]["accounts"].append(acc["project_id"])
                    new_vid_entry = {
                        "video_id": vid_id,
                        "title": v_title,
                        "channel": v_channel,
                        "url": v_url,
                        "keyword": kw_label or "direct_target",
                        "account": acc["project_id"]
                    }
                    save_history(history, new_entry=new_vid_entry)

                    print(f"      ✅ [{acc['label']}] Comment posted successfully! (Saved to Supabase) Total: [{posted_count}/{max_comments}]")

                    # Wait inter-account delay if another account is about to post on the SAME video
                    has_more_accounts = (i < len(active_accs) - 1) and (posted_count < max_comments)
                    if has_more_accounts:
                        acc_delay = random.randint(12, 25)
                        print(f"      ⏳ Waiting {acc_delay}s before next account comments on this video...")
                        time.sleep(acc_delay)

        # Hybrid/Combo Mode: Also scan this same video for loan seekers and reply directly!
        if args.hybrid and account_mgr.has_active_accounts():
            print(f"\n   🔍 [HYBRID COMBO] Scanning comments on this video for emergency loan seekers...")
            lead_replies = scan_and_reply_leads_on_video(
                youtube_acc_mgr=account_mgr,
                v_info=v_info,
                config=config,
                args=args,
                lead_history=lead_history,
                max_leads=3
            )
            if lead_replies > 0:
                print(f"   🎯 Successfully replied to {lead_replies} loan seekers on this video!")
            else:
                print(f"   ℹ️ No pending loan seeker questions found on this video.")

        return video_success_count

    # Category 1: Emergency Loan Seeker Lead Reply Mode
    if args.reply_leads:
        run_lead_seeker_bot(
            account_mgr=account_mgr,
            config=config,
            args=args,
            max_comments=max_comments,
            min_delay=min_delay,
            max_delay=max_delay,
            keywords=keywords,
            days_back=days_back,
            max_results=max_results,
            region_code=region_code,
            orders_to_try=orders_to_try,
            max_pages=max_pages,
            using_public_search=using_public_search
        )
        return

    # 1. Direct Target Mode: if user provided a specific URL or video ID
    direct_target = args.url or args.video_id
    if direct_target:
        v_id = extract_video_id(direct_target)
        print(f"\n🎯 Direct target specified: Video ID {v_id}")

        active_list = account_mgr.get_active_accounts()
        first_svc = account_mgr.get_service_for(active_list[0]) if (active_list and not args.dry_run) else None
        video_info = get_video_details(first_svc, v_id) if first_svc else {"id": v_id, "title": f"Video {v_id}", "channel": "YouTube", "url": direct_target}

        post_multi_account_to_video(video_info, kw_label="direct_target")

        print("\n" + "=" * 65)
        print(f"🎉 Run completed! Total comments processed: {posted_count}")
        print("=" * 65 + "\n")
        return

    # 2. Automated Search Mode: iterate through keywords and search orders
    shuffled_keywords = list(keywords)
    random.shuffle(shuffled_keywords)

    for kw in shuffled_keywords:
        if posted_count >= max_comments or not account_mgr.has_active_accounts():
            break

        for current_order in orders_to_try:
            if posted_count >= max_comments or not account_mgr.has_active_accounts():
                break

            search_mode_label = "Zero-Quota Public" if using_public_search else "YouTube API"
            print(f"\n🔍 Searching videos for: '{kw}' [mode: {search_mode_label}, sort: {current_order}]...")

            active_list = account_mgr.get_active_accounts()
            search_svc = account_mgr.get_service_for(active_list[0]) if (active_list and not using_public_search) else None

            status, videos = search_target_videos(
                search_svc,
                keyword=kw,
                days_back=days_back,
                max_results=max_results,
                region_code=region_code,
                order=current_order,
                relevance_language=relevance_language,
                max_pages=max_pages,
                force_public=using_public_search
            )

            if status == "QUOTA_FALLBACK":
                using_public_search = True

            print(f"   Found {len(videos)} videos.")

            for video in videos:
                if posted_count >= max_comments or not account_mgr.has_active_accounts():
                    break

                video_id = video["id"]
                past_record = history.get(video_id, {})
                posted_accs = past_record.get("accounts", []) if isinstance(past_record, dict) else []

                eligible_accs = [
                    a for a in account_mgr.get_active_accounts()
                    if args.ignore_history or a["project_id"] not in posted_accs
                ]
                if not eligible_accs:
                    skipped_history_count += 1
                    continue

                negative_keywords = search_cfg.get("negative_keywords", [])
                title_lower = video["title"].lower()
                if any(neg.lower() in title_lower for neg in negative_keywords):
                    continue

                comments_made = post_multi_account_to_video(video, kw_label=kw, order_label=current_order)

                if comments_made > 0 and posted_count < max_comments and account_mgr.has_active_accounts():
                    sleep_seconds = random.randint(min_delay, max_delay)
                    print(f"\n   ⏳ Video complete! Sleeping {sleep_seconds}s before next video...")
                    time.sleep(sleep_seconds)

    print("\n" + "=" * 65)
    print(f"🎉 Run completed! Total comments processed: {posted_count}")
    if skipped_history_count > 0:
        print(f"⏩ Videos skipped (already in history.json): {skipped_history_count}")
    print("=" * 65)

    if not account_mgr.has_active_accounts():
        print("\n⚠️  ALL YOUTUBE DAILY COMMENTING QUOTAS EXCEEDED")
        print(f"All {account_mgr.total_accounts} configured Google Cloud API projects reached their comment limit.")
        print("Aap ek aur project banakar 'jsons/' folder me JSON add kar sakte hain,")
        print("ya rozana quota reset hone (midnight Pacific Time, ~1:30 PM IST) tak wait karein.\n")
    elif posted_count == 0:
        print("\n💡 TIP: Agar comments 0 rahe, to in options ko use karein:")
        print("   1. Zero-Quota Public Search force karein:")
        print("      python3 scripts/marketing-bot/youtube_comment_bot.py --public-search --limit 10")
        print("   2. Specific new keyword par search karein:")
        print("      python3 scripts/marketing-bot/youtube_comment_bot.py --keyword 'kreditbee loan app' --days 90")
        print("   3. Kisi bhi direct YouTube video par comment post karein:")
        print("      python3 scripts/marketing-bot/youtube_comment_bot.py --url 'https://www.youtube.com/watch?v=VIDEO_ID'")
        print("   4. History ignore karke comment karein:")
        print("      python3 scripts/marketing-bot/youtube_comment_bot.py --ignore-history --limit 5")
        print("   5. History reset karein (purani history ka automatic backup ban jayega):")
        print("      python3 scripts/marketing-bot/youtube_comment_bot.py --clear-history -y\n")


if __name__ == "__main__":
    main()
