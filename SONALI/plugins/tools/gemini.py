import re
import os
import sys
import asyncio
import time
import threading
from io import StringIO
from flask import Flask, request, jsonify
from pyrogram import Client, filters
from yt_dlp import YoutubeDL

# Import configuration and main app core
import config
from SONALI import app

# ==========================================================
# FLASK API ENGINE & ENDPOINT
# ==========================================================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({
        "status": "running",
        "endpoints": {
            "download_api": "/download [POST]"
        }
    }), 200

@flask_app.route('/download', methods=['POST'])
def download_api_endpoint():
    """
    Endpoint: http://YOUR_VPS_IP:8080/download
    Method: POST
    JSON Body: { "url": "https://www.instagram.com/reel/..." }
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Missing 'url' parameter in JSON body"}), 400
    
    video_url = data['url']
    
    # Run the metadata scraping engine synchronously for the API response
    try:
        metadata = get_instagram_all_data(video_url)
        if not metadata.get("video_url"):
            return jsonify({"status": "failed", "reason": "Content restricted or invalid link"}), 400
            
        return jsonify({
            "status": "success",
            "uploader": metadata.get("uploader"),
            "title": metadata.get("title"),
            "duration_seconds": metadata.get("duration"),
            "views": metadata.get("view_count"),
            "likes": metadata.get("like_count"),
            "direct_download_url": metadata.get("video_url")
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def run_flask():
    # Runs the API on port 8080
    flask_app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

# ==========================================================
# SECONDARY TELEGRAM BOT INITIALIZATION
# ==========================================================
insta_bot = Client(
    "insta_downloader_session", 
    api_id=config.INSTA_API_ID, 
    api_hash=config.INSTA_API_HASH, 
    bot_token=config.INSTA_BOT_TOKEN
)

INSTAGRAM_REGEX = r".*(instagram\.com|instagr\.am)/(p|reel|tv|share)/[^\s]+"

current_status_msg = None
last_edit_time = 0
loop_engine = None

COOKIES_DATA = """
# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	0	sessionid	YOUR_ACTUAL_SESSION_ID_HERE
.instagram.com	TRUE	/	TRUE	0	ds_user_id	YOUR_USER_ID_HERE
"""
CLEANED_COOKIES = COOKIES_DATA.strip()

def create_progress_bar(percentage):
    total_blocks = 10
    filled_blocks = int(percentage / 10)
    empty_blocks = total_blocks - filled_blocks
    return f"[{'⬛' * filled_blocks}{'⬜' * empty_blocks}] {percentage}%"

def yt_dlp_callback(d):
    global current_status_msg, last_edit_time, loop_engine
    if d['status'] == 'downloading' and current_status_msg and loop_engine:
        total = d.get('total_bytes') or d.get('total_bytes_estimate')
        downloaded = d.get('downloaded_bytes', 0)
        if total:
            percentage = int((downloaded / total) * 100)
            bar = create_progress_bar(percentage)
            speed = d.get('speed', 0)
            speed_str = f"{speed / (1024 * 1024):.2f} MB/s" if speed else "Scraping..."
            now = time.time()
            if now - last_edit_time > 2.0:
                last_edit_time = now
                try:
                    asyncio.run_coroutine_threadsafe(
                        current_status_msg.edit(
                            f"📥 **Downloading Media File...**\n\n"
                            f"🎬 **Progress:** `{bar}`\n"
                            f"⚡ **Speed:** `{speed_str}`"
                        ),
                        loop_engine
                    )
                except Exception:
                    pass

async def pyrogram_upload_callback(current, total, status_msg):
    global last_edit_time
    now = time.time()
    if now - last_edit_time > 2.0:
        last_edit_time = now
        percentage = int((current / total) * 100)
        bar = create_progress_bar(percentage)
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        try:
            await status_msg.edit(
                f"📤 **Uploading to Telegram Server...**\n\n"
                f"🚀 **Progress:** `{bar}`\n"
                f"📦 **Size:** `{current_mb:.2f} MB` / `{total_mb:.2f} MB`"
            )
        except Exception:
            pass

def get_instagram_all_data(url):
    clean_url = url.split("?")[0].strip().rstrip("/")
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'quiet': True,
        'no_warnings': True,
        'get_comments': True,
        'http_headers': {
            'User-Agent': 'Instagram 311.0.0.32.118 Android (33/13; 450dpi; 1080x2216; Samsung; SM-S908B; q2q; qcom; en_US; 548232598)',
        }
    }
    if "sessionid" in CLEANED_COOKIES.lower():
        ydl_opts['cookiefile'] = StringIO(CLEANED_COOKIES)

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(clean_url, download=False)
            video_url = info.get('url') or (info['formats'][-1]['url'] if 'formats' in info else None)
            real_caption = info.get('description') or info.get('title') or info.get('alt_title') or 'No Caption'
            metadata = {
                "video_url": video_url,
                "title": real_caption.strip(),
                "uploader": info.get('uploader', 'Unknown_User'),
                "duration": info.get('duration'),
                "view_count": info.get('view_count', 'N/A'),
                "like_count": info.get('like_count', 'N/A'),
                "id": info.get('id') or str(int(time.time())),
                "comments": []
            }
            return metadata
        except Exception as e:
            return {"video_url": None}

def download_video_locally(url, video_id):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'video_{video_id}.mp4',
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [yt_dlp_callback],
    }
    if "sessionid" in CLEANED_COOKIES.lower():
        ydl_opts['cookiefile'] = StringIO(CLEANED_COOKIES)
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return f'video_{video_id}.mp4'

@insta_bot.on_message(filters.text & filters.regex(INSTAGRAM_REGEX))
async def auto_detect_instagram_link(client, message):
    global current_status_msg, last_edit_time, loop_engine
    match = re.search(r'(https?://[^\s]+)', message.text)
    if not match: return
        
    url = match.group(1)
    status_msg = await message.reply_text("⚡ **Link detected!** Querying server data...")
    loop_engine = asyncio.get_event_loop()
    current_status_msg = status_msg
    last_edit_time = 0

    data = await loop_engine.run_in_executor(None, get_instagram_all_data, url)
    if not data.get("video_url"):
        await status_msg.edit("❌ **Extraction Failed!** Content restricted or link broken.")
        return

    dur = data.get("duration")
    duration_str = f"{int(float(dur)) // 60}:{int(float(dur)) % 60:02d} Mins" if dur else "N/A"
    
    caption = (
        f"⚡ **Instagram Reel Downloaded** ⚡\n\n"
        f"👤 **Uploader :** @{data.get('uploader')}\n"
        f"⏰ **Duration :** {duration_str}\n"
    )

    try:
        file_path = await loop_engine.run_in_executor(None, download_video_locally, url, data["id"])
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            await status_msg.edit("📤 **Download complete! Initializing Telegram upload channel...**")
            await message.reply_video(
                video=file_path, 
                caption=caption,
                progress=pyrogram_upload_callback,
                progress_args=(status_msg,)
            )
            await status_msg.delete()
            os.remove(file_path)
    except Exception as e:
        await status_msg.edit(f"❌ Pipeline broke down during workflow.\nError: {e}")

# ==========================================================
# TIMING HOOKS
# ==========================================================
@app.on_start()
async def start_everything(client):
    print("[INFO] - Launching Flask Web Engine on Port 8080...")
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("[INFO] - Starting Secondary Instagram Bot...")
    await insta_bot.start()

@app.on_stop()
async def stop_everything(client):
    await insta_bot.stop()
