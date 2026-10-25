"""
Supabase Database Helper for NovaBorrow Marketing Automation
Handles persistence of:
1. Videos commented (marketing_videos)
2. Loan leads replied (marketing_leads)
3. Bot instances configuration (marketing_instances)
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import execute_values, Json

# Supabase connection string
# Can be overridden with SUPABASE_DB_URL environment variable
DEFAULT_CONN_STR = "postgresql://postgres:%2339DGAKT%23eMbjNg@db.uhgzgbkovachkdiaudfx.supabase.co:5432/postgres"
DATABASE_URL = os.environ.get("SUPABASE_DB_URL", DEFAULT_CONN_STR)

logger = logging.getLogger("supabase_db")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def get_connection():
    """Create a new PostgreSQL connection to Supabase."""
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)


def init_db():
    """Create required tables and indexes in Supabase if they do not exist."""
    sql = """
    CREATE TABLE IF NOT EXISTS marketing_videos (
        video_id VARCHAR(64) PRIMARY KEY,
        title TEXT,
        channel TEXT,
        url TEXT,
        keyword TEXT,
        accounts TEXT[] DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_marketing_videos_created ON marketing_videos (created_at DESC);

    CREATE TABLE IF NOT EXISTS marketing_leads (
        comment_id VARCHAR(128) PRIMARY KEY,
        video_id VARCHAR(64),
        video_title TEXT,
        author TEXT,
        query TEXT,
        reply TEXT,
        account TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_marketing_leads_video ON marketing_leads (video_id);
    CREATE INDEX IF NOT EXISTS idx_marketing_leads_created ON marketing_leads (created_at DESC);

    CREATE TABLE IF NOT EXISTS marketing_instances (
        instance_id VARCHAR(64) PRIMARY KEY,
        name TEXT,
        accounts TEXT[] DEFAULT '{}',
        mode VARCHAR(32) DEFAULT 'both',
        keyword TEXT,
        status VARCHAR(32) DEFAULT 'stopped',
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        logger.info("Supabase database tables verified / created successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Supabase DB: {e}")
        return False


def sync_local_history_to_supabase(history_file: str, lead_file: str):
    """
    Migrates/Syncs existing JSON history files into Supabase tables without data loss.
    Uses ON CONFLICT DO UPDATE so it is safe to run multiple times.
    """
    video_count = 0
    lead_count = 0

    # 1. Sync videos history
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)

            video_records = []
            for vid, item in history_data.items():
                video_records.append((
                    vid,
                    item.get("title", ""),
                    item.get("channel", ""),
                    item.get("url", f"https://www.youtube.com/watch?v={vid}"),
                    item.get("keyword", ""),
                    item.get("accounts", []),
                    item.get("timestamp")
                ))

            if video_records:
                sql_videos = """
                INSERT INTO marketing_videos (video_id, title, channel, url, keyword, accounts, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()))
                ON CONFLICT (video_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    channel = EXCLUDED.channel,
                    url = EXCLUDED.url,
                    keyword = EXCLUDED.keyword,
                    accounts = (
                        SELECT ARRAY(
                            SELECT DISTINCT UNNEST(marketing_videos.accounts || EXCLUDED.accounts)
                        )
                    ),
                    updated_at = NOW();
                """
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        for rec in video_records:
                            cur.execute(sql_videos, rec)
                    conn.commit()
                video_count = len(video_records)
                logger.info(f"Successfully synced {video_count} videos to Supabase.")
        except Exception as e:
            logger.error(f"Error syncing history.json to Supabase: {e}")

    # 2. Sync lead reply history
    if os.path.exists(lead_file):
        try:
            with open(lead_file, "r", encoding="utf-8") as f:
                lead_data = json.load(f)

            lead_records = []
            for cid, item in lead_data.items():
                lead_records.append((
                    cid,
                    item.get("video_id", ""),
                    item.get("video_title", ""),
                    item.get("author", ""),
                    item.get("query", ""),
                    item.get("reply", ""),
                    item.get("account", ""),
                    item.get("timestamp")
                ))

            if lead_records:
                sql_leads = """
                INSERT INTO marketing_leads (comment_id, video_id, video_title, author, query, reply, account, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()))
                ON CONFLICT (comment_id) DO NOTHING;
                """
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        for rec in lead_records:
                            cur.execute(sql_leads, rec)
                    conn.commit()
                lead_count = len(lead_records)
                logger.info(f"Successfully synced {lead_count} lead replies to Supabase.")
        except Exception as e:
            logger.error(f"Error syncing lead_reply_history.json to Supabase: {e}")

    return {"videos_synced": video_count, "leads_synced": lead_count}


def fetch_all_videos_from_supabase() -> Dict[str, Dict[str, Any]]:
    """Loads all video history from Supabase into standard dict format."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT video_id, title, channel, url, keyword, accounts, updated_at
                    FROM marketing_videos
                """)
                rows = cur.fetchall()
                result = {}
                for r in rows:
                    result[r[0]] = {
                        "title": r[1],
                        "channel": r[2],
                        "url": r[3],
                        "keyword": r[4],
                        "accounts": r[5] if r[5] else [],
                        "timestamp": r[6].isoformat() if r[6] else None
                    }
                return result
    except Exception as e:
        logger.error(f"Error fetching videos from Supabase: {e}")
        return {}


def fetch_all_leads_from_supabase() -> Dict[str, Dict[str, Any]]:
    """Loads all lead reply history from Supabase into standard dict format."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT comment_id, video_id, video_title, author, query, reply, account, created_at
                    FROM marketing_leads
                """)
                rows = cur.fetchall()
                result = {}
                for r in rows:
                    result[r[0]] = {
                        "video_id": r[1],
                        "video_title": r[2],
                        "author": r[3],
                        "query": r[4],
                        "reply": r[5],
                        "account": r[6],
                        "timestamp": r[7].isoformat() if r[7] else None
                    }
                return result
    except Exception as e:
        logger.error(f"Error fetching leads from Supabase: {e}")
        return {}


def save_video_to_supabase(video_id: str, title: str, channel: str, url: str, keyword: str, account: str):
    """Upserts a single video comment record into Supabase."""
    sql = """
    INSERT INTO marketing_videos (video_id, title, channel, url, keyword, accounts, updated_at)
    VALUES (%s, %s, %s, %s, %s, ARRAY[%s], NOW())
    ON CONFLICT (video_id) DO UPDATE SET
        title = EXCLUDED.title,
        channel = EXCLUDED.channel,
        url = EXCLUDED.url,
        keyword = EXCLUDED.keyword,
        accounts = (
            SELECT ARRAY(
                SELECT DISTINCT UNNEST(marketing_videos.accounts || ARRAY[EXCLUDED.accounts[1]])
            )
        ),
        updated_at = NOW();
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (video_id, title, channel, url, keyword, account))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving video {video_id} to Supabase: {e}")
        return False


def save_lead_to_supabase(comment_id: str, video_id: str, video_title: str, author: str, query: str, reply: str, account: str):
    """Inserts a single loan seeker lead reply into Supabase."""
    sql = """
    INSERT INTO marketing_leads (comment_id, video_id, video_title, author, query, reply, account, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (comment_id) DO NOTHING;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (comment_id, video_id, video_title, author, query, reply, account))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving lead {comment_id} to Supabase: {e}")
        return False


def get_marketing_stats_from_supabase() -> Dict[str, Any]:
    """Fetches real-time marketing statistics aggregated directly from Supabase."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Total videos & sum of accounts posted per video
                cur.execute("""
                    SELECT 
                        COUNT(*), 
                        COALESCE(SUM(CARDINALITY(accounts)), 0)
                    FROM marketing_videos
                """)
                v_row = cur.fetchone()
                total_videos = v_row[0] if v_row else 0
                total_video_comments = v_row[1] if v_row else 0

                # Total leads
                cur.execute("SELECT COUNT(*) FROM marketing_leads")
                l_row = cur.fetchone()
                total_leads = l_row[0] if l_row else 0

                # Recent activity
                cur.execute("""
                    SELECT video_id, title, channel, url, keyword, accounts, updated_at
                    FROM marketing_videos
                    ORDER BY updated_at DESC
                    LIMIT 15
                """)
                recent_rows = cur.fetchall()
                recent_list = []
                for r in recent_rows:
                    recent_list.append({
                        "id": r[0],
                        "title": r[1] or "Video",
                        "channel": r[2] or "",
                        "url": r[3] or f"https://www.youtube.com/watch?v={r[0]}",
                        "keyword": r[4] or "",
                        "accounts": r[5] or [],
                        "timestamp": r[6].strftime("%Y-%m-%d %H:%M:%S") if r[6] else ""
                    })

                return {
                    "total_commented_videos": total_videos,
                    "total_lead_replies": total_leads,
                    "total_comments_posted": total_video_comments + total_leads,
                    "recent_activity": recent_list,
                    "source": "supabase"
                }
    except Exception as e:
        logger.error(f"Error fetching stats from Supabase: {e}")
        return {}


def save_instance_to_supabase(instance_id: str, name: str, accounts: List[str], mode: str, keyword: str, status: str):
    """Saves or updates instance configuration in Supabase."""
    sql = """
    INSERT INTO marketing_instances (instance_id, name, accounts, mode, keyword, status, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (instance_id) DO UPDATE SET
        name = EXCLUDED.name,
        accounts = EXCLUDED.accounts,
        mode = EXCLUDED.mode,
        keyword = EXCLUDED.keyword,
        status = EXCLUDED.status,
        updated_at = NOW();
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (instance_id, name, accounts, mode, keyword, status))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving instance {instance_id} to Supabase: {e}")
        return False


def load_instances_from_supabase() -> List[Dict[str, Any]]:
    """Loads all saved instances from Supabase."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT instance_id, name, accounts, mode, keyword, status
                    FROM marketing_instances
                    ORDER BY instance_id ASC
                """)
                rows = cur.fetchall()
                result = []
                for r in rows:
                    result.append({
                        "id": r[0],
                        "name": r[1],
                        "accounts": r[2] or [],
                        "mode": r[3] or "both",
                        "keyword": r[4] or "",
                        "status": r[5] or "stopped"
                    })
                return result
    except Exception as e:
        logger.error(f"Error loading instances from Supabase: {e}")
        return []
