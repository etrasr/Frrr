#!/usr/bin/env python3
import time
import requests
import os
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth

# --- CONFIGURATION ---
ETHIOPIA_TZ = timezone(timedelta(hours=3))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Updated Hardcoded Token
SESSION_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6OTYxMDc3LCJmX25hbWUiOiIrMjUxOTUxNTAyNTAxIiwibF9uYW1lIjoiIiwiZV9tYWlsIjoiIiwiYWN0aXZlIjoxLCJhdmF0YXIiOm51bGwsInVzZXJuYW1lIjoiKzI1MTk1MTUwMjUwMSIsInRpbWV6b25lIjpudWxsLCJiYWxhbmNlIjoiMC4yMiIsInVuaXRzIjoiNS4wMCIsImJpcnRoZGF5IjoiMjAwMC0wOC0wNVQyMTowMDowMC4wMDBaIiwiZ2VuZGVyIjoiTkEiLCJwaG9uZSI6IisyNTE5NTE1MDI1MDEiLCJhZGRyZXNzIjpudWxsLCJjaXR5IjpudWxsLCJjb3VudHJ5IjoiRVRISU9QSUEiLCJjdXJyZW5jeSI6IkVUQiIsImNyZWF0ZWQiOiIyMDIzLTEyLTA1VDE2OjMyOjA1LjAwMFoiLCJraW5kIjoiSU5URVJORVQiLCJiZXR0aW5nX2FsbG93ZWQiOjEsImxvY2FsZSI6ImVuIiwibW9uaXRvcmVkIjowLCJiZXRsaW1pdCI6Ii0xIiwibGl2ZV9kZWxheSI6MCwiZGVsZXRlZCI6MCwiZGVsZXRlZF9hdCI6bnVsbCwidiI6MSwibm90aWZ5X2N0b2tlbiI6ImV5SmhiR2NpT2lKSVV6STFOaUlzSW5SNWNDSTZJa3BYVkNKOS5leUp6ZFdJaU9pSTVOakV3TnpjaUxDSnBZWFFpT2pFM05qUTFPVGt6TVRCOS42enA2dUliTzBlSHZ0MF9KVmFUUkRBN0tsMmU1ci1CYTJES19tQURGdERNIiwiaWF0IjoxNzY0NTk5MzEwLCJleHAiOjE3NjQ2ODU3MTB9.FiaCkCFCA84XDVlkEbe9U39mrN8uI9w-YDl5VvBqywU"

GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"
BASE_URL = "https://flashsport.bet"

# --- BOT STATE ---
bot_state = {
    "driver": None,
    "flashes_detected": 0,
    "session_start": None,
    "in_results_phase": False,
    "daily_flashes": 0,
    "last_daily_report": time.time(),
    "start_timestamp": time.time()
}

def eth_time():
    return datetime.now(ETHIOPIA_TZ).strftime("%H:%M:%S")

def log_msg(msg):
    ts = eth_time()
    print(f"[{ts}] {msg}", flush=True)

def send_to_telegram(image_path, caption):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        log_msg("⚠️ Telegram credentials missing")
        return False
    try:
        with open(image_path, 'rb') as photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            files = {'photo': photo}
            data = {'chat_id': CHAT_ID, 'caption': caption}
            response = requests.post(url, files=files, data=data, timeout=15)
            if response.status_code == 200:
                log_msg(f"✅ Sent photo: {caption[:50]}")
                return True
            else:
                log_msg(f"❌ Telegram photo error: {response.status_code}")
                return False
    except Exception as e:
        log_msg(f"❌ Telegram photo failed: {str(e)[:50]}")
        return False

def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {'chat_id': CHAT_ID, 'text': text}
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except:
        return False

def count_green_pixels(image_path):
    try:
        img = Image.open(image_path).convert('RGB')
        pixels = img.load()
        width, height = img.size
        
        green_count = 0
        # Scan every 3rd pixel to save CPU
        for x in range(0, width, 3):
            for y in range(0, height, 3):
                r, g, b = pixels[x, y]
                # Detection logic for bright green flash
                if g > 200 and r < 100 and b < 100:
                    green_count += 1
        return green_count
    except Exception as e:
        log_msg(f"❌ Count error: {str(e)[:50]}")
        return 0

def detect_green_flash(image_path):
    green_count = count_green_pixels(image_path)
    # Range for flash (not result screen)
    if 50 < green_count < 300:
        return True
    return False

def is_results_phase(image_path):
    green_count = count_green_pixels(image_path)
    # If lots of green, it's the result screen showing all 20 numbers
    return green_count > 300

def setup_chrome():
    log_msg("🚀 Starting Chrome...")
    
    chrome_bin = None
    chromedriver_bin = None
    
    # Auto-detect binaries
    try:
        result = subprocess.run(['which', 'chromium'], capture_output=True, text=True, timeout=3)
        chrome_bin = result.stdout.strip() if result.stdout else None
    except: pass
    
    try:
        result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True, timeout=3)
        chromedriver_bin = result.stdout.strip() if result.stdout else None
    except: pass
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    
    if chrome_bin:
        options.binary_location = chrome_bin
    
    try:
        service = Service(executable_path=chromedriver_bin) if chromedriver_bin else None
        driver = webdriver.Chrome(service=service, options=options) if service else webdriver.Chrome(options=options)
        
        stealth(driver, languages=["en-US"], vendor="Google Inc.", platform="Win32")
        driver.set_page_load_timeout(45)
        driver.set_script_timeout(45)
        
        log_msg("✅ Chrome ready")
        return driver
    except Exception as e:
        log_msg(f"❌ Chrome setup failed: {str(e)[:50]}")
        raise

def get_latest_update_id():
    if not TELEGRAM_TOKEN: return 0
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get('ok') and data.get('result'):
            return data['result'][-1]['update_id']
        return 0
    except:
        return 0

def handle_telegram_commands():
    log_msg("📱 Telegram command listener started")
    update_id = get_latest_update_id()
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {'offset': update_id + 1, 'timeout': 30}
            response = requests.get(url, params=params, timeout=35)
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    update_id = update['update_id']
                    if 'message' not in update: continue
                    
                    message = update['message']
                    text = message.get('text', '').strip()
                    
                    if text == '/screenshot':
                        if bot_state["driver"]:
                            try:
                                img_path = f"/tmp/manual_{int(time.time())}.png"
                                bot_state["driver"].save_screenshot(img_path)
                                send_to_telegram(img_path, f"📸 Requested Snapshot | {eth_time()}")
                            except: send_telegram_message("❌ Cannot take screenshot now")
                        else:
                            send_telegram_message("⚠️ Bot initializing...")
                    
                    elif text == '/status':
                        uptime_mins = (time.time() - bot_state["start_timestamp"]) / 60
                        msg = (f"📊 KENO BOT STATUS\n"
                               f"🕒 Time: {eth_time()}\n"
                               f"⏱️ Uptime: {int(uptime_mins // 60)}h {int(uptime_mins % 60)}m\n"
                               f"⚡ Flashes (Session): {bot_state['flashes_detected']}\n"
                               f"📅 Flashes (Today): {bot_state['daily_flashes']}")
                        send_telegram_message(msg)
            
            time.sleep(1)
        except:
            time.sleep(5)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"KENO BOT v6 LIVE")
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args): pass

# --- MODIFIED: Uses Render's PORT variable ---
def start_web_server():
    # Render assigns a port via the PORT environment variable.
    # We must use that, otherwise the web service won't be accessible.
    port = int(os.environ.get("PORT", 10000))
    log_msg(f"🌐 Starting web server on port {port}...")
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    except Exception as e:
        log_msg(f"⚠️ Web server error: {e}")

def monitor_game():
    log_msg("🟢 KENO BOT v6 STARTED")
    
    session_retry = 0
    
    while True:
        driver = None
        try:
            session_retry += 1
            log_msg(f"📍 Starting Session #{session_retry}")
            
            driver = setup_chrome()
            bot_state["driver"] = driver
            
            # 1. Login Logic
            log_msg("🔐 Injecting Session Token...")
            driver.get(BASE_URL)
            time.sleep(2)
            
            driver.add_cookie({
                "name": "token",
                "value": SESSION_TOKEN,
                "domain": "flashsport.bet",
                "path": "/"
            })
            
            driver.get(BASE_URL) # Refresh to apply cookie
            time.sleep(3)
            
            # 2. Check Token Validity
            current_url = driver.current_url
            if "auth" in current_url or "login" in current_url or "Sign" in driver.title:
                log_msg("❌ TOKEN EXPIRED OR INVALID - Cannot Login!")
                send_telegram_message("🚨 CRITICAL: Keno Session Token Expired! Bot cannot login. Please update token.")
                # Sleep long to avoid spamming if token is dead
                time.sleep(300) 
                driver.quit()
                continue
            
            log_msg("✅ Login Successful")
            driver.get(GAME_URL)
            time.sleep(5)
            
            # Reset session counters
            bot_state["session_start"] = time.time()
            bot_state["flashes_detected"] = 0
            in_results_phase = False
            last_heartbeat = time.time()
            
            # --- MONITORING LOOP ---
            while (time.time() - bot_state["session_start"]) < 14400: # Restart browser every 4 hours
                try:
                    # A. Daily Report Check
                    if time.time() - bot_state["last_daily_report"] > 86400: # 24 Hours
                        report_msg = (f"📅 DAILY FLASH REPORT\n"
                                      f"----------------------\n"
                                      f"Total Flashes: {bot_state['daily_flashes']}\n"
                                      f"Time: {eth_time()}")
                        send_telegram_message(report_msg)
                        bot_state["daily_flashes"] = 0
                        bot_state["last_daily_report"] = time.time()

                    # B. Get Screenshot
                    img_path = f"/tmp/scan_{int(time.time()*100)}.png"
                    driver.save_screenshot(img_path)
                    
                    # C. Check for Game Session Expiry (Text on screen)
                    page_source = driver.page_source
                    if "YOUR GAME SESSION EXPIRED" in page_source:
                        log_msg("⚠️ GAME SESSION EXPIRED detected on screen. Reloading...")
                        break # Breaks inner loop, triggers browser restart

                    # D. Flash Detection
                    is_results = is_results_phase(img_path)
                    
                    if is_results:
                        if not in_results_phase:
                            log_msg("⏸️ Results Phase")
                            in_results_phase = True
                    else:
                        if in_results_phase:
                            log_msg("▶️ Countdown Phase Resumed")
                            in_results_phase = False
                        
                        if detect_green_flash(img_path):
                            bot_state["flashes_detected"] += 1
                            bot_state["daily_flashes"] += 1
                            
                            caption = f"🟢 FLASH DETECTED | {eth_time()}"
                            if send_to_telegram(img_path, caption):
                                log_msg(f"🚨 FLASH SENT! (Session: {bot_state['flashes_detected']})")
                            
                            time.sleep(0.5) # Avoid double alerts
                    
                    # E. Heartbeat Logging (Every 60 sec)
                    if time.time() - last_heartbeat > 60:
                        log_msg(f"💓 Heartbeat: Active | Daily: {bot_state['daily_flashes']} | Session: {bot_state['flashes_detected']}")
                        last_heartbeat = time.time()
                        
                    time.sleep(1)
                    
                except Exception as e:
                    log_msg(f"⚠️ Loop error: {str(e)[:50]}")
                    time.sleep(1)
            
            log_msg("♻️ Scheduled Browser Restart")
            
        except Exception as e:
            log_msg(f"❌ Critical Session Error: {str(e)[:50]}")
            time.sleep(5)
        
        finally:
            if driver:
                try: driver.quit()
                except: pass
            bot_state["driver"] = None
            time.sleep(5)

def main():
    start_web_server()
    threading.Thread(target=handle_telegram_commands, daemon=True).start()
    monitor_game()

if __name__ == "__main__":
    main()
