import re
import os
import sys
import random
import asyncio
import time
import requests
from io import StringIO
from pyrogram import Client, filters
from pyrogram.enums import ChatAction
from yt_dlp import YoutubeDL

# Config aur APIs standard structures import
from config import BANNED_USERS
from PurviAPI import api as purvi_api  
from MukeshAPI import api as mukesh_api  
from SONALI import app

# --- AUTO UPDATE DEPENDENCY ENGINE ---
try:
    os.system(f"{sys.executable} -m pip install --upgrade yt-dlp")
except Exception as e:
    print(f"Dependency auto-update failed: {e}")

# --- GLOBAL VARIABLES & STATE TRACKING ---
INSTAGRAM_REGEX = r".*(instagram.com|instagr.am)/(p|reel|tv|share)/[^\s]+"
current_status_msg = None
last_edit_time = 0

# --- AUTHENTICATED PROXIES LIST ---
PROXY_LIST = [
    "http://zbgnspng:l75251a9tnum@38.154.203.95:5863",
    "http://zbgnspng:l75251a9tnum@198.105.121.200:6462",
    "http://zbgnspng:l75251a9tnum@64.137.96.74:6641",
    "http://zbgnspng:l75251a9tnum@209.127.138.10:5784",
    "http://zbgnspng:l75251a9tnum@38.154.185.97:6370",
    "http://zbgnspng:l75251a9tnum@84.247.60.125:6095",
    "http://zbgnspng:l75251a9tnum@142.111.67.146:5611",
    "http://zbgnspng:l75251a9tnum@191.96.254.138:6185",
    "http://zbgnspng:l75251a9tnum@31.58.9.4:6077",
    "http://zbgnspng:l75251a9tnum@104.239.107.47:5699"
]

# --- LIVE REAL INSTAGRAM COOKIES DATA ---
COOKIES_DATA = """# Netscape HTTP Cookie File
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
.instagram.com	TRUE	/	TRUE	0	rur	"SNB\\05425349046417\\0541812519658:01fffc9637faa298604a83c726eeea0db1be399feb6739f78b44fa57fa6ae6e555759255"
"""
CLEANED_COOKIES = COOKIES_DATA.strip()

# --- UTILITIES ---

def create_progress_bar(percentage):
    total_blocks = 10
    filled_blocks = int(percentage / 10)
    empty_blocks = total_blocks - filled_blocks
    return f"[{'⬛' * filled_blocks}{'⬜' * empty_blocks}] {percentage}%"

def yt_dlp_callback(d):
    global current_status_msg, last_edit_time
    if d['status'] == 'downloading' and current_status_msg:
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
                    loop = app.loop or asyncio.get_event_loop()
                    asyncio.run_coroutine_threadsafe(  
                        current_status_msg.edit(  
                            f"📥 **Downloading Media File...**\n\n"  
                            f"🎬 **Progress:** `{bar}`\n"  
                            f"⚡ **Speed:** `{speed_str}`"  
                        ),  
                        loop  
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
    selected_proxy = random.choice(PROXY_LIST)
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'get_comments': True,
        'proxy': selected_proxy,
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
            if real_caption and "Window" in real_caption:   
                real_caption = info.get('title', 'No Caption')  

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
            print(f"Metadata Restricted Block: {e}")  
            return {  
                "video_url": None, "title": "Restricted / Age-Gated Content", "uploader": "Restricted_Audience",  
                "duration": None, "view_count": "N/A", "like_count": "N/A", "id": str(int(time.time())),  
                "comments": ["💬 System: Top comments hidden for restricted links."]  
            }

def download_video_locally(url, video_id):
    selected_proxy = random.choice(PROXY_LIST)
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'video_{video_id}.mp4',
        'quiet': True,
        'no_warnings': True,
        'proxy': selected_proxy,
        'progress_hooks': [yt_dlp_callback],
    }

    if "sessionid" in CLEANED_COOKIES.lower():  
        ydl_opts['cookiefile'] = StringIO(CLEANED_COOKIES)  
          
    with YoutubeDL(ydl_opts) as ydl:  
        ydl.download([url])  
    return f'video_{video_id}.mp4'


# --- HANDLERS & PLUGINS ---

# 1. Instagram Auto Downloader Plugin Hook
@app.on_message(filters.text & filters.regex(INSTAGRAM_REGEX) & ~BANNED_USERS)
async def auto_detect_instagram_link(client, message):
    global current_status_msg, last_edit_time
    
    match = re.search(r'(https?://[^\s]+)', message.text)  
    if not match: return  
          
    url = match.group(1)  
    status_msg = await message.reply_text("⚡ **Link detected!** Querying server data...")  
    
    loop_engine = asyncio.get_running_loop()  
    current_status_msg = status_msg  
    last_edit_time = 0  

    data = await loop_engine.run_in_executor(None, get_instagram_all_data, url)  

    dur = data.get("duration")  
    duration_str = f"{int(float(dur)) // 60}:{int(float(dur)) % 60:02d} Mins" if dur else "N/A"  
      
    likes = data.get("like_count", "N/A")  
    likes_str = f"{likes:,}" if isinstance(likes, int) else str(likes)  
      
    views = data.get("view_count", "N/A")  
    views_str = f"{views:,}" if isinstance(views, int) else str(views)  
      
    caption = (  
        f"⚡ **Instagram Reel Downloaded** ⚡\n\n"  
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
            await status_msg.edit("📤 **Download complete! Initializing Telegram upload channel...**")  
              
            await message.reply_video(  
                video=file_path,   
                caption=caption,  
                progress=pyrogram_upload_callback,  
                progress_args=(status_msg,)  
            )  
              
            await status_msg.delete()  
            os.remove(file_path)  
        else:  
            await status_msg.edit("❌ **Extraction Failed!** Invalid or expired cookies parse setup.")  
            if os.path.exists(file_path): os.remove(file_path)  
              
    except Exception as e:  
        await status_msg.edit(f"❌ Pipeline broke down during workflow.\nError: {e}")


# 2. ChatGPT AI Plugin Hook
@app.on_message(filters.command(["chatgpt", "ai", "ask"]) & ~BANNED_USERS)
async def chatgpt_chat(bot, message):
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text(
            "Example:\n\n`/ai write simple website code using html css, js?`"
        )
        return

    if message.reply_to_message and message.reply_to_message.text:
        user_input = message.reply_to_message.text
    else:
        user_input = " ".join(message.command[1:])

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        results = await purvi_api.chatgpt(user_input)
        await message.reply_text(results)
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


# 3. Gemini AI Plugin Hook
@app.on_message(filters.command(["gemini"]) & ~BANNED_USERS)
async def gemini_handler(client, message):
    await app.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    if (
        message.text.startswith(f"/gemini@{app.username}")
        and len(message.text.split(" ", 1)) > 1
    ):
        user_input = message.text.split(" ", 1)[1]
    elif message.reply_to_message and message.reply_to_message.text:
        user_input = message.reply_to_message.text
    else:
        if len(message.command) > 1:
            user_input = " ".join(message.command[1:])
        else:
            await message.reply_text("ᴇxᴀᴍᴘʟᴇ :- /gemini who is lord ram")
            return

    try:  
        response = mukesh_api.gemini(user_input)  
        await app.send_chat_action(message.chat.id, ChatAction.TYPING)  
        x = response.get("results")  
        if x:  
            await message.reply_text(x, quote=True)  
        else:  
            await message.reply_text("sᴏʀʀʏ sɪʀ! ᴘʟᴇᴀsᴇ Tʀʏ ᴀɢᴀɪɴ")  
    except requests.exceptions.RequestException:  
        await message.reply_text("❌ API Server Connection Error.")
    except Exception as e:
        await message.reply_text(f"❌ Process Error: {e}")


# --- PLUGIN STRUCT METADATA ---
__MODULE__ = "Aɪ & Uᴛɪʟs"
__HELP__ = """
/ai [ǫᴜᴇʀʏ] - ᴀsᴋ ʏᴏᴜʀ ǫᴜᴇsᴛɪᴏɴ ᴡɪᴛʜ ᴄʜᴀᴛɢᴘᴛ's ᴀɪ
/gemini [ǫᴜᴇʀʏ] - ᴀsᴋ ʏᴏᴜʀ ǫᴜᴇsᴛɪᴏɴ ᴡɪᴛʜ ɢᴏᴏɢʟᴇ's ɢᴇᴍɪɴɪ ᴀɪ

ℹ️ **Instagram Auto Downloader**:
Simply paste any Instagram reel/post link in the chat, and the bot will auto-download and upload it for you!
"""
            
