#!/usr/bin/env python3
"""
NovaBorrow Marketing Bot - Multi-Instance Scalable Cloud Control Center
Supports running multiple parallel instances (e.g. 2 JSONs per instance, 3+ parallel workers)
Powered by aiohttp.web
"""

import os
import sys
import json
import asyncio
import secrets
import shutil
import re
import pickle
from datetime import datetime
from collections import deque
from aiohttp import web, WSMsgType

# Base Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import supabase_db
except Exception:
    supabase_db = None

BOT_DIR = os.path.join(BASE_DIR, "marketing-bot")
JSONS_DIR = os.path.join(BOT_DIR, "jsons")
STATIC_DIR = os.path.join(BASE_DIR, "static")
SELECTED_ACCOUNTS_FILE = os.path.join(BOT_DIR, "selected_accounts.json")
INSTANCES_FILE = os.path.join(BOT_DIR, "instances.json")
CONFIG_FILE = os.path.join(BOT_DIR, "config.json")
HISTORY_FILE = os.path.join(BOT_DIR, "history.json")
LEAD_HISTORY_FILE = os.path.join(BOT_DIR, "lead_reply_history.json")

os.makedirs(JSONS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Authentication Configuration
DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "admin")
DASHBOARD_PASS = os.environ.get("DASHBOARD_PASS", "novaborrow2026")
AUTH_TOKENS = set()

# Multi-Instance Process Management
running_instances = {}  # { instance_id: { "process": proc, "pid": pid, "start_time": iso, "name": name, "accounts": [] } }
log_buffer = deque(maxlen=1000)
ws_clients = set()

# Helper: Broadcast to WebSockets with Instance Tagging
async def broadcast_log(line: str, instance_id: str = "system", instance_name: str = "SYSTEM"):
    entry = {
        "type": "log",
        "instance_id": instance_id,
        "instance_name": instance_name,
        "data": line,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }
    log_buffer.append(entry)
    if ws_clients:
        dead_clients = set()
        for ws in list(ws_clients):
            try:
                await ws.send_json(entry)
            except Exception:
                dead_clients.add(ws)
        ws_clients.difference_update(dead_clients)

# Helper: Get Token File for Client Secret
def get_token_file(client_secret_path: str) -> str:
    base = os.path.basename(client_secret_path)
    name, _ = os.path.splitext(base)
    if name == "client_secret":
        return os.path.join(BOT_DIR, "token.pickle")
    try:
        with open(client_secret_path, "r", encoding="utf-8") as f:
            s_data = json.load(f)
            proj_id = (
                s_data.get("installed", {}).get("project_id")
                or s_data.get("web", {}).get("project_id")
            )
            if proj_id:
                return os.path.join(BOT_DIR, f"token_{proj_id}.pickle")
    except Exception:
        pass
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    return os.path.join(BOT_DIR, f"token_{clean_name[:30]}.pickle")

# Helper: Discover all client secrets
def find_all_client_secrets():
    candidates = []
    primary = os.path.join(BOT_DIR, "client_secret.json")
    if os.path.exists(primary):
        candidates.append(primary)

    for fname in sorted(os.listdir(BOT_DIR)):
        if fname.startswith("client_secret") and fname.endswith(".json") and not fname.endswith(".example.json"):
            full = os.path.join(BOT_DIR, fname)
            if full not in candidates and os.path.isfile(full):
                candidates.append(full)

    if os.path.isdir(JSONS_DIR):
        for root, _, files in os.walk(JSONS_DIR):
            for fname in sorted(files):
                if fname.endswith(".json") and not fname.endswith(".example.json"):
                    full = os.path.join(root, fname)
                    if full not in candidates and os.path.isfile(full):
                        candidates.append(full)
    return candidates

# Helper: Load / Save Instances
def load_instances():
    all_secrets = find_all_client_secrets()
    local_instances = []
    if os.path.exists(INSTANCES_FILE):
        try:
            with open(INSTANCES_FILE, "r", encoding="utf-8") as f:
                local_instances = json.load(f)
                if isinstance(local_instances, list) and len(local_instances) > 0:
                    return local_instances
        except Exception:
            pass

    # Try Supabase if local file empty
    if supabase_db:
        try:
            sb_insts = supabase_db.load_instances_from_supabase()
            if sb_insts and len(sb_insts) > 0:
                return sb_insts
        except Exception:
            pass

    # Default initial setup if no instances configured yet
    return [
        {
            "id": "inst_1",
            "name": "Instance #1",
            "accounts": all_secrets[:2] if len(all_secrets) >= 2 else all_secrets,
            "mode": "hybrid",
            "keyword": "",
            "max_comments": 25,
            "min_delay": 30,
            "max_delay": 60,
            "public_search": True,
            "ignore_history": False
        }
    ]

def save_instances(instances_list):
    try:
        with open(INSTANCES_FILE, "w", encoding="utf-8") as f:
            json.dump(instances_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Error saving instances: {e}")

    # Synchronize instances to Supabase
    if supabase_db:
        try:
            for inst in instances_list:
                supabase_db.save_instance_to_supabase(
                    instance_id=inst.get("id"),
                    name=inst.get("name", "Instance"),
                    accounts=inst.get("accounts", []),
                    mode=inst.get("mode", "both"),
                    keyword=inst.get("keyword", ""),
                    status=inst.get("status", "stopped")
                )
        except Exception as e:
            print(f"[!] Error syncing instances to Supabase: {e}")

# Helper: Account Details Extractor
def inspect_account(secret_path: str):
    project_id = "unknown"
    client_id = "unknown"
    client_type = "unknown"
    valid_json = False

    try:
        with open(secret_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            node = data.get("installed") or data.get("web")
            if node:
                valid_json = True
                client_type = "installed" if "installed" in data else "web"
                project_id = node.get("project_id", "unknown")
                client_id = node.get("client_id", "unknown")
    except Exception:
        pass

    token_path = get_token_file(secret_path)
    token_exists = os.path.exists(token_path)
    is_authenticated = False
    auth_detail = "Needs Authentication"

    if token_exists:
        try:
            with open(token_path, "rb") as tf:
                creds = pickle.load(tf)
                if creds:
                    if creds.valid:
                        is_authenticated = True
                        auth_detail = "Active & Valid"
                    elif creds.expired and creds.refresh_token:
                        is_authenticated = True
                        auth_detail = "Expired (Auto-Refreshable)"
                    else:
                        auth_detail = "Expired (Re-login required)"
        except Exception as e:
            auth_detail = f"Corrupted Token ({e})"

    rel_path = os.path.relpath(secret_path, BASE_DIR)

    return {
        "filepath": secret_path,
        "relpath": rel_path,
        "filename": os.path.basename(secret_path),
        "project_id": project_id,
        "client_id": client_id,
        "client_type": client_type,
        "valid_json": valid_json,
        "token_filename": os.path.basename(token_path),
        "token_path": token_path,
        "token_exists": token_exists,
        "is_authenticated": is_authenticated,
        "auth_detail": auth_detail
    }

# Session verification
def check_auth(request):
    cookie_token = request.cookies.get("nb_token")
    header_token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    token = cookie_token or header_token
    return token in AUTH_TOKENS

# Stream Subprocess Output for an Instance
async def stream_instance_output(instance_id: str, instance_name: str, proc):
    await broadcast_log(f"⚡ [{instance_name}] Process started (PID: {proc.pid})", instance_id, instance_name)
    
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace").rstrip()
        await broadcast_log(text, instance_id, instance_name)

    exit_code = await proc.wait()
    if instance_id in running_instances:
        del running_instances[instance_id]
    await broadcast_log(f"🛑 [{instance_name}] Process terminated (Exit code: {exit_code})", instance_id, instance_name)

# ----------------- HTTP HANDLERS -----------------

async def handle_login(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Invalid JSON"}, status=400)

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if username == DASHBOARD_USER and password == DASHBOARD_PASS:
        token = secrets.token_hex(24)
        AUTH_TOKENS.add(token)
        response = web.json_response({"success": True, "token": token, "user": username})
        response.set_cookie("nb_token", token, max_age=86400 * 30, httponly=False, samesite="Lax")
        return response
    return web.json_response({"success": False, "message": "Galat Username ya Password!"}, status=401)

async def handle_logout(request):
    token = request.cookies.get("nb_token")
    if token and token in AUTH_TOKENS:
        AUTH_TOKENS.remove(token)
    response = web.json_response({"success": True})
    response.del_cookie("nb_token")
    return response

async def handle_auth_check(request):
    authenticated = check_auth(request)
    return web.json_response({"authenticated": authenticated, "user": DASHBOARD_USER if authenticated else None})

async def handle_get_accounts(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    all_secrets = find_all_client_secrets()
    accounts = [inspect_account(p) for p in all_secrets]

    return web.json_response({
        "success": True,
        "accounts": accounts,
        "total": len(accounts),
        "authenticated_count": sum(1 for a in accounts if a["is_authenticated"])
    })

async def handle_upload_credentials(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    reader = await request.multipart()
    uploaded_files = []

    while True:
        part = await reader.next()
        if part is None:
            break
        if part.filename:
            filename = os.path.basename(part.filename)
            if filename.endswith(".json"):
                target_path = os.path.join(JSONS_DIR, filename)
            elif filename.endswith(".pickle"):
                target_path = os.path.join(BOT_DIR, filename)
            else:
                target_path = os.path.join(JSONS_DIR, filename)

            with open(target_path, "wb") as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    f.write(chunk)
            uploaded_files.append(filename)

    return web.json_response({
        "success": True,
        "message": f"{len(uploaded_files)} file(s) successfully uploaded!",
        "files": uploaded_files
    })

async def handle_delete_account(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        target_path = data.get("filepath")
    except Exception:
        return web.json_response({"error": "Invalid request"}, status=400)

    if not target_path or not os.path.exists(target_path):
        return web.json_response({"error": "File not found"}, status=404)

    if not os.path.abspath(target_path).startswith(os.path.abspath(BOT_DIR)):
        return web.json_response({"error": "Unauthorized file operation"}, status=403)

    token_path = get_token_file(target_path)
    try:
        os.remove(target_path)
        if os.path.exists(token_path):
            os.remove(token_path)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    # Remove from any configured instances
    instances = load_instances()
    for inst in instances:
        inst["accounts"] = [p for p in inst.get("accounts", []) if p != target_path and os.path.basename(p) != os.path.basename(target_path)]
    save_instances(instances)

    return web.json_response({"success": True, "message": "Account removed successfully"})

async def handle_get_oauth_url(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        secret_path = data.get("filepath")
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    if not secret_path or not os.path.exists(secret_path):
        return web.json_response({"error": "Client secret not found"}, status=404)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        flow = InstalledAppFlow.from_client_secrets_file(
            secret_path,
            scopes=SCOPES,
            redirect_uri="http://localhost"
        )
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="true"
        )
        return web.json_response({
            "success": True,
            "auth_url": auth_url,
            "account": os.path.basename(secret_path)
        })
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_submit_oauth_code(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        secret_path = data.get("filepath")
        code = data.get("code", "").strip()
    except Exception:
        return web.json_response({"error": "Invalid request"}, status=400)

    if not secret_path or not code:
        return web.json_response({"error": "Missing secret path or auth code"}, status=400)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        flow = InstalledAppFlow.from_client_secrets_file(
            secret_path,
            scopes=SCOPES,
            redirect_uri="http://localhost"
        )
        if "code=" in code:
            code = code.split("code=")[1].split("&")[0]

        flow.fetch_token(code=code)
        credentials = flow.credentials
        token_path = get_token_file(secret_path)
        with open(token_path, "wb") as f:
            pickle.dump(credentials, f)

        return web.json_response({
            "success": True,
            "message": f"Account authenticated! Token saved to {os.path.basename(token_path)}"
        })
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

# ----------------- MULTI-INSTANCE ENDPOINTS -----------------

async def handle_get_instances(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    instances = load_instances()
    result = []

    for inst in instances:
        iid = inst["id"]
        is_running = iid in running_instances and running_instances[iid]["process"].returncode is None
        proc_data = running_instances.get(iid, {})

        result.append({
            **inst,
            "status": "running" if is_running else "stopped",
            "pid": proc_data.get("pid"),
            "start_time": proc_data.get("start_time")
        })

    return web.json_response({
        "success": True,
        "instances": result,
        "total_instances": len(result),
        "running_count": len(running_instances)
    })

async def handle_save_instances(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        instances_list = data.get("instances", [])
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    save_instances(instances_list)
    return web.json_response({"success": True, "message": "Instances saved successfully"})

async def handle_auto_split_instances(request):
    """Automatically groups all uploaded accounts into instances of N accounts each (e.g. 2 per instance)."""
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        per_inst = int(data.get("accounts_per_instance", 2))
    except Exception:
        per_inst = 2

    if per_inst < 1:
        per_inst = 2

    all_secrets = find_all_client_secrets()
    if not all_secrets:
        return web.json_response({"success": False, "message": "Koi client secret JSON file nahi mili!"}, status=400)

    new_instances = []
    chunk_idx = 1
    for i in range(0, len(all_secrets), per_inst):
        chunk = all_secrets[i:i + per_inst]
        new_instances.append({
            "id": f"inst_{chunk_idx}",
            "name": f"Instance #{chunk_idx} (Worker {chunk_idx})",
            "accounts": chunk,
            "mode": "hybrid",
            "keyword": "",
            "max_comments": 25,
            "min_delay": 30,
            "max_delay": 60,
            "public_search": True,
            "ignore_history": False
        })
        chunk_idx += 1

    save_instances(new_instances)
    return web.json_response({
        "success": True,
        "message": f"Successfully created {len(new_instances)} parallel instances ({per_inst} accounts each)!",
        "instances": new_instances
    })

async def handle_create_instance(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    instances = load_instances()
    new_num = len(instances) + 1
    new_inst = {
        "id": f"inst_{secrets.token_hex(3)}",
        "name": f"Instance #{new_num}",
        "accounts": [],
        "mode": "hybrid",
        "keyword": "",
        "max_comments": 25,
        "min_delay": 30,
        "max_delay": 60,
        "public_search": True,
        "ignore_history": False
    }
    instances.append(new_inst)
    save_instances(instances)
    return web.json_response({"success": True, "instance": new_inst})

async def handle_delete_instance(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        inst_id = data.get("instance_id")
    except Exception:
        return web.json_response({"error": "Invalid request"}, status=400)

    # Stop instance if currently running
    if inst_id in running_instances:
        try:
            running_instances[inst_id]["process"].kill()
            del running_instances[inst_id]
        except Exception:
            pass

    instances = load_instances()
    instances = [i for i in instances if i["id"] != inst_id]
    save_instances(instances)
    return web.json_response({"success": True, "message": "Instance deleted"})

async def launch_instance_process(inst_conf):
    inst_id = inst_conf["id"]
    inst_name = inst_conf.get("name", f"Instance-{inst_id}")
    accounts = inst_conf.get("accounts", [])

    # Filter existing
    valid_accounts = [p for p in accounts if os.path.exists(p)]
    if not valid_accounts:
        raise ValueError(f"Instance '{inst_name}' me koi valid client secret JSON file selected nahi hai!")

    cmd = [
        sys.executable,
        "-u",
        os.path.join(BOT_DIR, "youtube_comment_bot.py"),
        "--secrets",
        ",".join(valid_accounts),
        "--instance-id",
        inst_name.replace(" ", "_")
    ]

    mode = inst_conf.get("mode", "hybrid")
    if mode == "hybrid":
        cmd.append("--hybrid")
    elif mode == "leads":
        cmd.append("--reply-leads")

    if inst_conf.get("public_search", True):
        cmd.append("--public-search")
    if inst_conf.get("ignore_history", False):
        cmd.append("--ignore-history")
    if inst_conf.get("keyword"):
        cmd.extend(["--keyword", inst_conf.get("keyword").strip()])

    sub_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=BASE_DIR,
        env=sub_env
    )

    running_instances[inst_id] = {
        "process": proc,
        "pid": proc.pid,
        "start_time": datetime.now().isoformat(),
        "name": inst_name,
        "accounts": [os.path.basename(p) for p in valid_accounts]
    }

    asyncio.create_task(stream_instance_output(inst_id, inst_name, proc))
    return proc.pid

async def handle_start_instance(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        inst_id = data.get("instance_id")
    except Exception:
        return web.json_response({"error": "Invalid request"}, status=400)

    if inst_id in running_instances and running_instances[inst_id]["process"].returncode is None:
        return web.json_response({"success": False, "message": f"Instance {inst_id} is already running!"}, status=400)

    instances = load_instances()
    target_conf = next((i for i in instances if i["id"] == inst_id), None)
    if not target_conf:
        return web.json_response({"error": "Instance not found"}, status=404)

    try:
        pid = await launch_instance_process(target_conf)
        return web.json_response({"success": True, "message": f"{target_conf.get('name')} started!", "pid": pid})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=500)

async def handle_stop_instance(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        inst_id = data.get("instance_id")
    except Exception:
        return web.json_response({"error": "Invalid request"}, status=400)

    if inst_id not in running_instances:
        return web.json_response({"success": True, "message": "Instance is already stopped"})

    try:
        inst_item = running_instances.get(inst_id)
        if not inst_item:
            return web.json_response({"success": True, "message": "Instance is already stopped"})
        proc = inst_item["process"]
        inst_name = inst_item.get("name", inst_id)
        proc.terminate()
        await broadcast_log(f"⚠️ [{inst_name}] Stopping instance...", inst_id, inst_name)
        try:
            await asyncio.wait_for(proc.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            proc.kill()
        running_instances.pop(inst_id, None)
        return web.json_response({"success": True, "message": f"{inst_name} stopped successfully"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=500)

async def handle_start_all_instances(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    instances = load_instances()
    started = []
    errors = []

    for inst in instances:
        iid = inst["id"]
        if iid not in running_instances or running_instances[iid]["process"].returncode is not None:
            try:
                pid = await launch_instance_process(inst)
                started.append({"id": iid, "name": inst.get("name"), "pid": pid})
            except Exception as e:
                errors.append(f"{inst.get('name')}: {e}")

    return web.json_response({
        "success": True,
        "message": f"Started {len(started)} parallel instance(s)!" + (f" Errors: {', '.join(errors)}" if errors else ""),
        "started": started
    })

async def handle_stop_all_instances(request):
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    stopped_count = 0
    for iid, item in list(running_instances.items()):
        try:
            item["process"].terminate()
            stopped_count += 1
        except Exception:
            pass

    running_instances.clear()
    await broadcast_log("🛑 [SYSTEM] All running instances stopped.", "system", "SYSTEM")
    return web.json_response({"success": True, "message": f"Stopped {stopped_count} instance(s)"})

# Status & History
async def handle_get_status(request):
    # Try fetching real-time stats directly from Supabase
    if supabase_db:
        try:
            sb_stats = supabase_db.get_marketing_stats_from_supabase()
            if sb_stats and sb_stats.get("total_comments_posted", 0) > 0:
                return web.json_response({
                    "running_instances_count": len(running_instances),
                    "is_any_running": len(running_instances) > 0,
                    "stats": {
                        "total_comments_posted": sb_stats.get("total_comments_posted", 0),
                        "total_commented_videos": sb_stats.get("total_commented_videos", 0),
                        "total_lead_replies": sb_stats.get("total_lead_replies", 0)
                    },
                    "recent_activity": sb_stats.get("recent_activity", []),
                    "database": "supabase"
                })
        except Exception as e:
            print(f"[!] Supabase stats fetch error: {e}")

    history_count = 0
    total_video_comments = 0
    leads_count = 0
    recent_activity = []

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                h = json.load(f)
                history_count = len(h)
                total_video_comments = sum(len(v.get('accounts', [1])) for v in h.values())
                for vid, item in list(h.items())[-8:]:
                    recent_activity.append({
                        "video_id": vid,
                        "title": item.get("title", "YouTube Video"),
                        "channel": item.get("channel", "Channel"),
                        "accounts": item.get("accounts", []),
                        "timestamp": item.get("timestamp")
                    })
        except Exception:
            pass

    if os.path.exists(LEAD_HISTORY_FILE):
        try:
            with open(LEAD_HISTORY_FILE, "r", encoding="utf-8") as f:
                leads_count = len(json.load(f))
        except Exception:
            pass

    total_comments_posted = total_video_comments + leads_count

    return web.json_response({
        "running_instances_count": len(running_instances),
        "is_any_running": len(running_instances) > 0,
        "stats": {
            "total_comments_posted": total_comments_posted,
            "total_commented_videos": history_count,
            "total_lead_replies": leads_count
        },
        "recent_activity": list(reversed(recent_activity)),
        "database": "local"
    })

async def handle_websocket_logs(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)

    # Replay recent logs
    for entry in list(log_buffer):
        await ws.send_json(entry)

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                pass
            elif msg.type == WSMsgType.ERROR:
                pass
    finally:
        ws_clients.discard(ws)

    return ws

async def handle_index(request):
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return web.FileResponse(index_file)
    return web.Response(text="Dashboard loading...", content_type="text/html")

def init_app():
    app = web.Application(client_max_size=50 * 1024 * 1024)
    
    # Routes
    app.router.add_get("/", handle_index)
    app.router.add_post("/api/auth/login", handle_login)
    app.router.add_post("/api/auth/logout", handle_logout)
    app.router.add_get("/api/auth/check", handle_auth_check)
    app.router.add_get("/api/accounts", handle_get_accounts)
    app.router.add_post("/api/accounts/upload", handle_upload_credentials)
    app.router.add_post("/api/accounts/delete", handle_delete_account)
    app.router.add_post("/api/accounts/oauth-url", handle_get_oauth_url)
    app.router.add_post("/api/accounts/oauth-code", handle_submit_oauth_code)

    # Multi-Instance Routes
    app.router.add_get("/api/instances", handle_get_instances)
    app.router.add_post("/api/instances/save", handle_save_instances)
    app.router.add_post("/api/instances/auto-split", handle_auto_split_instances)
    app.router.add_post("/api/instances/create", handle_create_instance)
    app.router.add_post("/api/instances/delete", handle_delete_instance)
    app.router.add_post("/api/instances/start", handle_start_instance)
    app.router.add_post("/api/instances/stop", handle_stop_instance)
    app.router.add_post("/api/instances/start-all", handle_start_all_instances)
    app.router.add_post("/api/instances/stop-all", handle_stop_all_instances)

    # Status & WebSocket
    app.router.add_get("/api/bot/status", handle_get_status)
    app.router.add_get("/ws/logs", handle_websocket_logs)

    # Static assets
    app.router.add_static("/static/", STATIC_DIR)

    return app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    print("\n" + "=" * 65)
    print("      🚀 NOVABORROW MULTI-INSTANCE MARKETING CONTROL 🚀")
    print("=" * 65)
    print(f"Server starting on: http://{host}:{port}")
    print(f"Default Login: {DASHBOARD_USER} / {DASHBOARD_PASS}")
    print("=" * 65 + "\n")
    app = init_app()
    web.run_app(app, host=host, port=port)
