import re
import os
import time
import asyncio
from io import StringIO
from pyrogram import filters
from yt_dlp import YoutubeDL
from SONALI import app # SONALI ke structure ke liye import

# Regex pattern
INSTAGRAM_REGEX = r".*(instagram\.com|instagr\.am)/(p|reel|tv|share)/[^\s]+"

# Cookies - Isse waise hi rehne de jaisa tere original code mein tha
COOKIES_DATA = """
# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	0	sessionid	YOUR_ACTUAL_SESSION_ID_HERE
.instagram.com	TRUE	/	TRUE	0	ds_user_id	YOUR_USER_ID_HERE
"""
CLEANED_COOKIES = COOKIES_DATA.strip()

# Helper Functions
def create_progress_bar(percentage):
    total_blocks = 10
    filled_blocks = int(percentage / 10)
    empty_blocks = total_blocks - filled_blocks
    return f"[{'⬛' * filled_blocks}{'⬜' * empty_blocks}] {percentage}%"

async def pyrogram_upload_callback(current, total, status_msg):
    percentage = int((current / total) * 100)
    bar = create_progress_bar(percentage)
    current_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    try:
        await status_msg.edit(f"📤 **Uploading...**\n\n🚀 **Progress:** `{bar}`\n📦 `{current_mb:.2f} MB / {total_mb:.2f} MB`")
    except: pass

def get_instagram_all_data(url):
    clean_url = url.split("?")[0].strip().rstrip("/")
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'quiet': True,
        'get_comments': True,
        'http_headers': {'User-Agent': 'Instagram 311.0.0.32.118 Android (33/13; 450dpi; 1080x2216; Samsung; SM-S908B; q2q; qcom; en_US; 548232598)'},
    }
    if "sessionid" in CLEANED_COOKIES.lower():
        ydl_opts['cookiefile'] = StringIO(CLEANED_COOKIES)
    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(clean_url, download=False)
            metadata = {
                "url": info.get('url') or (info['formats'][-1]['url']),
                "title": (info.get('description') or info.get('title', 'No Caption')).strip(),
                "uploader": info.get('uploader', 'Unknown'),
                "duration": info.get('duration', 0),
                "view_count": info.get('view_count', 'N/A'),
                "like_count": info.get('like_count', 'N/A'),
                "id": info.get('id', str(int(time.time()))),
                "comments": []
            }
            raw_comments = info.get('comments', [])
            for c in sorted(raw_comments, key=lambda x: x.get('like_count', 0), reverse=True)[:10]:
                metadata["comments"].append(f"💬 @{c.get('author', 'anon')}: {c.get('text', '').replace('\n', ' ')[:50]}")
            return metadata
        except Exception as e:
            return None

@app.on_message(filters.command(["ig", "reel", "reels", "instagram"]) | filters.regex(INSTAGRAM_REGEX))
async def ig_download(client, message):
    if message.command:
        if len(message.command) < 2: return await message.reply("❌ Link bhej bhai!")
        url = message.command[1]
    else:
        url = re.search(r'(https?://[^\s]+)', message.text).group(1)

    status_msg = await message.reply("⚡ **Querying server data...**")
    
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, get_instagram_all_data, url)
    if not data: return await status_msg.edit("❌ **Extraction Failed!** Check cookies.")

    dur = int(data.get("duration", 0))
    caption = (f"⚡ **Instagram Reel** ⚡\n\n👤 **Uploader:** @{data.get('uploader')}\n"
               f"⏰ **Duration:** {dur // 60}:{dur % 60:02d} Mins\n"
               f"👀 **Views:** {data.get('view_count')}\n❤️ **Likes:** {data.get('like_count')}\n\n"
               f"📝 **Caption:** {data.get('title')[:150]}...\n")
    if data["comments"]: caption += "\n📊 **Top Comments:**\n" + "\n".join(data["comments"])

    try:
        ydl_opts = {'format': 'best[ext=mp4]/best', 'outtmpl': f'vid_{data["id"]}.mp4', 'quiet': True}
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        file_path = f'vid_{data["id"]}.mp4'
        await status_msg.edit("📤 **Uploading to Telegram...**")
        await message.reply_video(
            video=file_path, 
            caption=caption[:1024],
            duration=dur,
            supports_streaming=True,
            progress=pyrogram_upload_callback,
            progress_args=(status_msg,)
        )
        await status_msg.delete()
        if os.path.exists(file_path): os.remove(file_path)
    except Exception as e:
        await status_msg.edit(f"❌ **Error:** {e}")
        
