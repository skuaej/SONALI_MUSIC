import re
import os
import time
import requests
from io import StringIO
from pyrogram import filters
from yt_dlp import YoutubeDL

# Main bot app ko SONALI se import kar rahe hain aur fallback loop ke liye asyncio
from SONALI import app
import asyncio

# Regex matching commands and plain links
INSTAGRAM_REGEX = r".*(instagram\.com|instagr\.am)/(p|reel|tv|share)/[^\s]+"

# Global reference variables tracking ke liye
current_status_msg = None
last_edit_time = 0
loop_engine = None

# ==========================================================
# 🍪 COOKIES TEXT AREA (Used for Backup Local Engine)
# ==========================================================
COOKIES_DATA = """
# Netscape HTTP Cookie File
# http://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.

.instagram.com	TRUE	/	TRUE	0	sessionid	YOUR_ACTUAL_SESSION_ID_HERE
.instagram.com	TRUE	/	TRUE	0	ds_user_id	YOUR_USER_ID_HERE
"""
# ==========================================================

CLEANED_COOKIES = COOKIES_DATA.strip()

def create_progress_bar(percentage):
    total_blocks = 10
    filled_blocks = int(percentage / 10)
    empty_blocks = total_blocks - filled_blocks
    return f"[{'⬛' * filled_blocks}{'⬜' * empty_blocks}] {percentage}%"

def yt_dlp_callback(d):
    """Local Download Progress Hook"""
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
                            f"📥 **Downloading Media File (Local Engine)...**\n\n"
                            f"🎬 **Progress:** `{bar}`\n"
                            f"⚡ **Speed:** `{speed_str}`"
                        ),
                        loop_engine
                    )
                except Exception:
                    pass

async def pyrogram_upload_callback(current, total, status_msg):
    """Telegram Upload Progress Hook (Both Cloud & Local)"""
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
    """Backup Engine: Local yt-dlp metadata extractor"""
    clean_url = url.split("?")[0].strip().rstrip("/")
    ydl_opts = {
        # Forced strictly to standard mp4 containers to prevent GIF generation
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 
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
            
            raw_comments = info.get('comments', [])
            if raw_comments:
                sorted_comments = sorted(raw_comments, key=lambda x: (x.get('like_count', 0), len(x.get('text', ''))), reverse=True)
                for c in sorted_comments:
                    author = c.get('author', 'anonymous_user')
                    text = c.get('text', '').strip().replace('\n', ' ')
                    if text: metadata["comments"].append(f"💬 @{author}: {text}")
                    if len(metadata["comments"]) >= 10: break
            return metadata
        except Exception as e:
            print(f"Local Metadata Extraction Failed: {e}")
            return None

def download_video_locally(url, video_id):
    """Backup Engine: Local yt-dlp downloader"""
    ydl_opts = {
        # Strictly merge and force mp4 block streams to clear up GIF flags
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
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


@app.on_message((filters.text & filters.regex(INSTAGRAM_REGEX)) | filters.command(["ig", "instagram", "reel"]))
async def auto_detect_instagram_link(client, message):
    global current_status_msg, last_edit_time, loop_engine
    
    if message.command and len(message.command) >= 2:
        url = message.text.split()[1]
    elif message.command and len(message.command) < 2:
        await message.reply_text("Pʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇ Iɴsᴛᴀɢʀᴀᴍ ʀᴇᴇʟ URL ᴀғᴛᴇ r ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅ")
        return
    else:
        match = re.search(r'(https?://[^\s]+)', message.text)
        if not match: return
        url = match.group(1)

    status_msg = await message.reply_text("⚡ **Link detected!** Launching Dual-Engine extraction...")
    
    loop_engine = asyncio.get_event_loop()
    current_status_msg = status_msg
    last_edit_time = 0

    # ------------------------------------------------------
    # ENGINE 1: CLOUD WORKERS API (Primary Engine)
    # ------------------------------------------------------
    print("🤖 [ENGINE 1] Trying Cloud API Server Extraction...")
    api_url = f"https://insta-dl.hazex.workers.dev/?url={url}"
    
    try:
        response = requests.get(api_url, timeout=10)
        result = response.json()
        
        if not result.get("error", True):
            data = result["result"]
            video_url = data["url"]
            
            # Formatting Cloud API duration output cleanly into raw seconds
            raw_dur = data.get("duration", "N/A")
            if raw_dur != "N/A":
                try:
                    duration_str = f"{int(float(raw_dur))} Seconds"
                except Exception:
                    duration_str = f"{raw_dur} Seconds"
            else:
                duration_str = "N/A"
                
            quality = data.get("quality", "N/A")
            size = data.get("formattedSize", "N/A")
            
            caption = (
                f"⚡ **Instagram Reel Downloaded (Cloud API)** ⚡\n\n"
                f"⏰ **Duration :** {duration_str}\n"
                f"🎬 **Quality :** {quality}\n"
                f"📦 **Size :** {size}\n"
            )
            
            await status_msg.edit("📤 **Cloud extraction successful! Initializing stream nodes...**")
            await message.reply_video(
                video=video_url,
                caption=caption,
                progress=pyrogram_upload_callback,
                progress_args=(status_msg,)
            )
            await status_msg.delete()
            return  
            
    except Exception as api_err:
        print(f"⚠️ [ENGINE 1 FAIL] Cloud API failed or timed out: {api_err}")

    # ------------------------------------------------------
    # ENGINE 2: LOCAL YT-DLP + COOKIES (Auto Fallback Engine)
    # ------------------------------------------------------
    print("🔄 [ENGINE 2] Fallback Triggered. Running Local Node Extraction...")
    await status_msg.edit("🔄 **Cloud API busy. Switching to Core Backup Local Engine...**")
    
    data = await loop_engine.run_in_executor(None, get_instagram_all_data, url)
    
    if not data or not data.get("video_url"):
        await status_msg.edit("❌ **Dual-Engine Extraction Failed!** Both systems rejected this link node.")
        return

    # Fixed local duration format to strictly show seconds
    dur = data.get("duration")
    duration_str = f"{int(float(dur))} Seconds" if dur else "N/A"
    
    likes = data.get("like_count", "N/A")
    likes_str = f"{likes:,}" if isinstance(likes, int) else str(likes)
    views = data.get("view_count", "N/A")
    views_str = f"{views:,}" if isinstance(views, int) else str(views)
    
    caption = (
        f"⚡ **Instagram Reel Downloaded (Backup Engine)** ⚡\n\n"
        f"👤 **Uploader :** @{data.get('uploader')}\n"
        f"⏰ **Duration :** {duration_str}\n"
        f"👀 **Views :** {views_str}\n"
        f"❤️ **Likes :** {likes_str}\n\n"
        f"📝 **Caption :** {data.get('title')[:200]}...\n"
    )
    if data.get("comments"):
        caption += "\n📊 **Top 10 User Comments:**\n" + "\n".join(data["comments"])
    if len(caption) > 1010: caption = caption[:970] + "\n\n...[Truncated]"

    try:
        file_path = await loop_engine.run_in_executor(None, download_video_locally, url, data["id"])
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            await status_msg.edit("📤 **Local download complete! Processing Telegram upload core...**")
            await message.reply_video(
                video=file_path, 
                caption=caption,
                progress=pyrogram_upload_callback,
                progress_args=(status_msg,)
            )
            await status_msg.delete()
            os.remove(file_path)
        else:
            await status_msg.edit("❌ **Fallback Extraction Failed!** Processing nodes returned empty caches.")
            if os.path.exists(file_path): os.remove(file_path)
            
    except Exception as e:
        await status_msg.edit(f"❌ Core processing failed during workflow execution.\nError: {e}")


MODULE = "Rᴇᴇʟ"
HELP = """
ɪɴsᴛᴀɢʀᴀᴍ ʀᴇᴇʟ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ:

• /ig [URL]: ᴅᴏᴡɴʟᴏᴀᴅ ɪɴsᴛᴀɢʀᴀᴍ ʀᴇᴇʟs. Pʀᴏᴠɪᴅᴇ ᴛʜᴇ ɪɴsᴛᴀɢʀᴀᴍ ʀᴇᴇʟ URL ᴀғᴛᴇʀ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅ.
• /instagram [URL]: ᴅᴏᴡɴʟᴏᴀᴅ ɪɴsᴛᴀɢʀᴀᴍ ʀᴇᴇʟs. Pʀᴏᴠɪᴅᴇ ᴛʜᴇ ɪɴsᴛᴀɢʀᴀᴍ ʀᴇᴇʟ URL ᴀғᴛᴇʀ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅ.
• /reel [URL]: ᴅᴏᴡɴʟᴏᴀᴅ ɪɴsᴛᴀɢʀᴀᴍ ʀᴇᴇʟs. Pʀᴏᴠɪᴅᴇ ᴛʜᴇ ɪɴsᴛᴀɢʀᴀᴍ ʀᴇᴇʟ URL ᴀғᴛᴇʀ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅ.
"""
