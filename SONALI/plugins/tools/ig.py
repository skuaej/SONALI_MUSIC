import re
import os
import asyncio
import time
from itertools import cycle
from io import StringIO
from pyrogram import filters
from pyrogram.enums import ChatAction
from yt_dlp import YoutubeDL
from SONALI import app

# ==========================================================
# 🌐 CONFIGURATION: PROXIES & COOKIES
# ==========================================================
RAW_PROXIES = [
    "38.154.203.95:5863:zbgnspng:l75251a9tnum",
    "198.105.121.200:6462:zbgnspng:l75251a9tnum",
    "64.137.96.74:6641:zbgnspng:l75251a9tnum",
    "209.127.138.10:5784:zbgnspng:l75251a9tnum"
]

def format_proxy(p_str):
    parts = p_str.split(":")
    return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"

PROXY_POOL = cycle([format_proxy(p) for p in RAW_PROXIES])
COOKIES_FILE = "instagram_cookies.txt"

# Ensure Cookies exist
if not os.path.exists(COOKIES_FILE):
    with open(COOKIES_FILE, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")

# ==========================================================
# 🛠️ HELPER FUNCTIONS
# ==========================================================

def create_progress_bar(pct):
    filled = int(pct / 10)
    return f"[{'⬛' * filled}{'⬜' * (10 - filled)}] {pct}%"

def get_yt_dlp_callback(status_msg, loop):
    last_edit = [0]
    def callback(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total:
                pct = int((d.get('downloaded_bytes', 0) / total) * 100)
                if time.time() - last_edit[0] > 2:
                    last_edit[0] = time.time()
                    try:
                        asyncio.run_coroutine_threadsafe(
                            status_msg.edit(f"📥 **Downloading...**\n`{create_progress_bar(pct)}`"), 
                            loop
                        )
                    except: pass
    return callback

# ==========================================================
# 🎬 MAIN HANDLER
# ==========================================================
@app.on_message(filters.text & filters.regex(r".*(instagram\.com|instagr\.am)/(p|reel|tv|share)/[^\s]+"))
async def insta_downloader(client, message):
    await app.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
    url = re.search(r'(https?://[^\s]+)', message.text).group(1)
    status_msg = await message.reply_text("⚡ **Analyzing link & fetching metadata...**")
    
    proxy = next(PROXY_POOL)
    loop = asyncio.get_running_loop()
    
    try:
        # 1. Fetch Metadata (Metadata, Comments, Caption)
        ydl_opts = {
            'format': 'best', 
            'proxy': proxy, 
            'quiet': True,
            'cookiefile': COOKIES_FILE,
            'extractor_args': {'instagram': ['get_comments']}
        }
        
        def extract():
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        data = await loop.run_in_executor(None, extract)
        file_name = f"video_{data['id']}.mp4"
        
        # Build Metadata Caption
        likes = data.get('like_count', 'N/A')
        views = data.get('view_count', 'N/A')
        duration = data.get('duration', 0)
        dur_str = f"{int(duration)//60}:{int(duration)%60:02d}"
        
        caption = (
            f"⚡ **Instagram Reel**\n\n"
            f"👤 **Uploader:** @{data.get('uploader', 'Unknown')}\n"
            f"⏰ **Duration:** {dur_str}\n"
            f"❤️ **Likes:** {likes}\n"
            f"👀 **Views:** {views}\n\n"
            f"📝 **Caption:** {data.get('title', 'No Caption')[:100]}\n"
        )
        
        # Parse Comments (Mc feature)
        comments = data.get('comments', [])
        if comments:
            caption += "\n📊 **Top Comments:**\n"
            for c in comments[:3]:
                clean_text = c.get('text', '').replace('\n', ' ')[:40]
                caption += f"💬 @{c.get('author', 'user')}: {clean_text}\n"

        # 2. Download
        await status_msg.edit("📥 **Downloading content...**")
        download_opts = {
            'format': 'best', 
            'proxy': proxy, 
            'outtmpl': file_name,
            'cookiefile': COOKIES_FILE,
            'progress_hooks': [get_yt_dlp_callback(status_msg, loop)]
        }
        await loop.run_in_executor(None, lambda: YoutubeDL(download_opts).download([url]))
        
        # 3. Upload
        if os.path.exists(file_name):
            await status_msg.edit("📤 **Uploading to Telegram...**")
            await message.reply_video(
                video=file_name, 
                caption=caption
            )
            await status_msg.delete()
            os.remove(file_name)
        else:
            await status_msg.edit("❌ **Error:** Download failed.")
            
    except Exception as e:
        await status_msg.edit(f"❌ **Error:** `{str(e)[:50]}`")
