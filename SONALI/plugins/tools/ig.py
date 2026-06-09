import re
import os
import asyncio
import time
import random
from pyrogram import filters
from pyrogram.enums import ChatAction
from yt_dlp import YoutubeDL
from SONALI import app

# ==========================================================
# 🌐 CONFIGURATION: COOKIES & PROXIES
# ==========================================================
COOKIES_DATA = r"""
# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.

.instagram.com	TRUE	/	TRUE	1815543658	csrftoken	UHOEPGsEWWZCyWaTiQREctWt6VCVpEi2
.instagram.com	TRUE	/	TRUE	1815543467	datr	q6YnagrdppRbnk_z74CLmql7
.instagram.com	TRUE	/	TRUE	1812519467	ig_did	83632560-C690-4FB6-8BF3-BD321873D9AF
.instagram.com	TRUE	/	TRUE	1781588459	wd	360x634
.instagram.com	TRUE	/	TRUE	1781588346	dpr	3
.instagram.com	TRUE	/	TRUE	1815543468	mid	aiemqwABAAF5b3O6W9brtE9zHHO0
.instagram.com	TRUE	/	TRUE	1788759658	ds_user_id	25349046417
.instagram.com	TRUE	/	TRUE	1812519546	sessionid	25349046417%3AelmMsdUhcSc1He%3A4%3AAYjZFTNLvevhBdQs48r-Bh5FxmIXO0yRu4uibe5kaw
.instagram.com	TRUE	/	TRUE	1815543547	ps_l	1
.instagram.com	TRUE	/	TRUE	1815543547	ps_n	1
.instagram.com	TRUE	/	TRUE	0	rur	"SNB\05425349046417\0541812519658:01fffc9637faa298604a83c726eeea0db1be399feb6739f78b44fa57fa6ae6e555759255"
"""

COOKIES_FILE = "instagram_cookies.txt"

# Automatically create the cookie file from the variable above
if not os.path.exists(COOKIES_FILE):
    with open(COOKIES_FILE, "w") as f:
        f.write(COOKIES_DATA.strip())

# All 10 Proxies
RAW_PROXIES = [
    "38.154.203.95:5863:zbgnspng:l75251a9tnum",
    "198.105.121.200:6462:zbgnspng:l75251a9tnum",
    "64.137.96.74:6641:zbgnspng:l75251a9tnum",
    "209.127.138.10:5784:zbgnspng:l75251a9tnum",
    "38.154.185.97:6370:zbgnspng:l75251a9tnum",
    "84.247.60.125:6095:zbgnspng:l75251a9tnum",
    "142.111.67.146:5611:zbgnspng:l75251a9tnum",
    "191.96.254.138:6185:zbgnspng:l75251a9tnum",
    "31.58.9.4:6077:zbgnspng:l75251a9tnum",
    "104.239.107.47:5699:zbgnspng:l75251a9tnum"
]

def format_proxy(p_str):
    parts = p_str.split(":")
    return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"

PROXY_LIST = [format_proxy(p) for p in RAW_PROXIES]

# ==========================================================
# 🛠️ HELPER FUNCTIONS
# ==========================================================

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
                            status_msg.edit(f"📥 **Downloading...** `{pct}%`"), 
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
    status_msg = await message.reply_text("⚡ **Analyzing link...**")
    
    # Pick random proxy
    proxy = random.choice(PROXY_LIST)
    loop = asyncio.get_running_loop()
    
    try:
        # 1. Fetch Metadata
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
        
        # Build Caption & Metadata
        likes = data.get('like_count', 0)
        views = data.get('view_count', 0)
        duration = data.get('duration', 0)
        dur_str = f"{int(duration)//60}:{int(duration)%60:02d}"
        
        caption = (
            f"⚡ **Instagram Reel**\n\n"
            f"👤 **Uploader:** @{data.get('uploader', 'Unknown')}\n"
            f"⏰ **Duration:** {dur_str}\n"
            f"❤️ **Likes:** {likes:,}\n"
            f"👀 **Views:** {views:,}\n\n"
            f"📝 **Caption:** {data.get('title', 'No Caption')[:150]}\n"
        )
        
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
            await message.reply_video(video=file_name, caption=caption)
            await status_msg.delete()
            os.remove(file_name)
        else:
            await status_msg.edit("❌ **Download failed.**")
            
    except Exception as e:
        await status_msg.edit(f"❌ **Error:** `{str(e)[:50]}`")
        
