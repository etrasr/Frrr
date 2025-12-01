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

ETHIOPIA_TZ = timezone(timedelta(hours=3))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SESSION_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6OTYxMDc3LCJmX25hbWUiOiIrMjUxOTUxNTAyNTAxIiwibF9uYW1lIjoiIiwiZV9tYWlsIjoiIiwiYWN0aXZlIjoxLCJhdmF0YXIiOm51bGwsInVzZXJuYW1lIjoiKzI1MTk1MTUwMjUwMSIsInRpbWV6b25lIjpudWxsLCJiYWxhbmNlIjoiMC4yMiIsInVuaXRzIjoiNS4wMCIsImJpcnRoZGF5IjoiMjAwMC0wOC0wNVQyMTowMDowMC4wMDBaIiwiZ2VuZGVyIjoiTkEiLCJwaG9uZSI6IisyNTE5NTE1MDI1MDEiLCJhZGRyZXNzIjpudWxsLCJjaXR5IjpudWxsLCJjb3VudHJ5IjoiRVRISU9QSUEiLCJjdXJyZW5jeSI6IkVUQiIsImNyZWF0ZWQiOiIyMDIzLTEyLTA1VDE2OjMyOjA1LjAwMFoiLCJraW5kIjoiSU5URVJORVQiLCJiZXR0aW5nX2FsbG93ZWQiOjEsImxvY2FsZSI6ImVuIiwibW9uaXRvcmVkIjowLCJiZXRsaW1pdCI6Ii0xIiwibGl2ZV9kZWxheSI6MCwiZGVsZXRlZCI6MCwiZGVsZXRlZF9hdCI6bnVsbCwiviI6MSwibm90aWZ5X2N0b2tlbiI6ImV5SmhiR2NpT2lKSVV6STFOaUlzSW5SNWNDSTZJa3BYVkNKOS5leUp6ZFdJaU9pSTVOakV3TnpjaUxDSnBZWFFpT2pFM05qUTFOemt5T0RTOS5UZlJyT2lsN0Fscm1aSXZZcUFpblhSX3RfQmNQbmVJZkJkN2RnQWFwQ2hjIiwiaWF0IjoxNzY0NTc5Mjg0LCJleHAiOjE3NjQ2NjU2ODR9.nwlc0-7RbhPbhAT0Ow7MVrC0lZo6w6Cjzh-rr54ThJI"

GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"
BASE_URL = "https://flashsport.bet"

bot_state = {
    "driver": None,
    "flashes_detected": 0,
    "session_start": None,
    "in_results_phase": False,
    "daily_flashes": 0,
    "last_daily_report": time.time(),
    "web_server_healthy": False,
    "session_expired_alert_sent": False,
    "failed_load_count": 0
}

def eth_time():
    return datetime.now(ETHIOPIA_TZ).strftime("%H:%M:%S")

def eth_date():
    return datetime.now(ETHIOPIA_TZ).strftime("%Y-%m-%d")

def log_msg(msg):
    ts = eth_time()
    print(f"[{ts}] {msg}", flush=True)

def send_to_telegram(image_path, caption):
    try:
        with open(image_path, 'rb') as photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            files = {'photo': photo}
            data = {'chat_id': CHAT_ID, 'caption': caption}
            response = requests.post(url, files=files, data=data, timeout=15)
            if response.status_code == 200:
                log_msg(f"✅ Sent: {caption[:50]}")
                return True
            else:
                log_msg(f"❌ Telegram error: {response.status_code}")
                return False
    except Exception as e:
        log_msg(f"❌ Telegram failed: {str(e)[:50]}")
        return False

def send_telegram_message(text):
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
        
        for x in range(0, width, 3):
            for y in range(0, height, 3):
                r, g, b = pixels[x, y]
                
                if g > 200 and r < 100 and b < 100:
                    green_count += 1
        
        return green_count
        
    except Exception as e:
        log_msg(f"❌ Count error: {str(e)[:50]}")
        return 0

def detect_green_flash(image_path):
    green_count = count_green_pixels(image_path)
    if 50 < green_count < 300:
        return True
    return False

def is_results_phase(image_path):
    green_count = count_green_pixels(image_path)
    return green_count > 300

def setup_chrome():
    log_msg("🚀 Starting Chrome...")
    
    chrome_bin = None
    chromedriver_bin = None
    
    try:
        result = subprocess.run(['which', 'chromium'], capture_output=True, text=True, timeout=3)
        chrome_bin = result.stdout.strip() if result.stdout else None
    except:
        pass
    
    try:
        result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True, timeout=3)
        chromedriver_bin = result.stdout.strip() if result.stdout else None
    except:
        pass
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    
    if chrome_bin:
        options.binary_location = chrome_bin
    
    try:
        service = Service(executable_path=chromedriver_bin) if chromedriver_bin else None
        driver = webdriver.Chrome(service=service, options=options) if service else webdriver.Chrome(options=options)
        
        stealth(driver, languages=["en-US"], vendor="Google Inc.", platform="Win32")
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(30)
        
        log_msg("✅ Chrome ready")
        return driver
    except Exception as e:
        log_msg(f"❌ Chrome setup failed: {str(e)[:50]}")
        raise

def get_latest_update_id():
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
                    
                    if 'message' not in update:
                        continue
                    
                    message = update['message']
                    text = message.get('text', '').strip()
                    
                    if text == '/screenshot':
                        log_msg("📸 /screenshot command received")
                        
                        if bot_state["driver"]:
                            try:
                                img_path = f"/tmp/keno_screenshot_{int(time.time())}.png"
                                bot_state["driver"].save_screenshot(img_path)
                                caption = f"📸 Screenshot requested | Time: {eth_time()}"
                                send_to_telegram(img_path, caption)
                            except Exception as e:
                                send_telegram_message(f"❌ Screenshot error: {str(e)[:50]}")
                        else:
                            send_telegram_message("⚠️ Bot not connected to game yet")
                    
                    elif text == '/status':
                        log_msg("📊 /status command received")
                        
                        if bot_state["session_start"]:
                            elapsed = (time.time() - bot_state["session_start"]) / 60
                            status_text = f"✅ BOT STATUS\n📍 Running: {int(elapsed)}min\n🟢 Today flashes: {bot_state['daily_flashes']}\n⏱️ Time: {eth_time()}"
                        else:
                            status_text = "⚠️ Bot starting..."
                        
                        send_telegram_message(status_text)
                    
                    elif text == '/help':
                        log_msg("ℹ️ /help command received")
                        help_text = """🎯 KENO BOT COMMANDS:
/screenshot - Get current game screenshot
/status - Show bot status & today flashes
/help - Show this message"""
                        send_telegram_message(help_text)
            
            time.sleep(1)
            
        except Exception as e:
            log_msg(f"⚠️ Command listener error: {str(e)[:50]}")
            time.sleep(5)

class HealthCheckHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        bot_state["web_server_healthy"] = True
        
        if self.path == '/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            try:
                elapsed_time = (time.time() - bot_state["session_start"]) / 60 if bot_state["session_start"] else 0
                health_data = f'{{"status": "ok", "flashes": {bot_state["daily_flashes"]}, "uptime_min": {int(elapsed_time)}}}'
                self.wfile.write(health_data.encode())
            except:
                self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format_string, *args):
        pass

def start_web_server():
    log_msg("🌐 Starting web server on port 10000...")
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        server.timeout = 30
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.daemon = True
        server_thread.start()
        log_msg("✅ Web server running - Uptime Robot can check /health")
    except Exception as e:
        log_msg(f"⚠️ Web server error: {str(e)[:50]}")

def monitor_game():
    log_msg("=" * 70)
    log_msg("🟢 KENO BOT v7 - GREEN FLASH DETECTION + AUTO-RELOAD")
    log_msg("=" * 70)
    log_msg("🔴 Commands: /screenshot, /status, /help")
    log_msg("❤️  24/7 heartbeat logging every 10 seconds")
    log_msg("📊 Auto-reloads game when session expires")
    
    session_retry = 0
    
    while True:
        driver = None
        try:
            session_retry += 1
            log_msg(f"📍 Session #{session_retry}")
            
            driver = setup_chrome()
            bot_state["driver"] = driver
            bot_state["failed_load_count"] = 0
            
            log_msg("🔐 Logging in...")
            driver.get(BASE_URL)
            time.sleep(1)
            driver.add_cookie({
                "name": "token",
                "value": SESSION_TOKEN,
                "domain": "flashsport.bet",
                "path": "/"
            })
            log_msg("✅ Session ready")
            
            log_msg("🎮 Loading game...")
            driver.get(GAME_URL)
            time.sleep(5)
            
            log_msg("⏱️  COUNTDOWN PHASE - Monitoring for green flashes")
            
            bot_state["session_start"] = time.time()
            bot_state["flashes_detected"] = 0
            bot_state["daily_flashes"] = 0
            bot_state["session_expired_alert_sent"] = False
            in_results_phase = False
            last_status_log = time.time()
            last_daily_report = time.time()
            last_heartbeat_log = time.time()
            scan_count = 0
            
            while (time.time() - bot_state["session_start"]) < 10800:
                try:
                    img_path = f"/tmp/keno_scan_{int(time.time() * 100)}.png"
                    
                    try:
                        driver.save_screenshot(img_path)
                        bot_state["failed_load_count"] = 0
                        
                        # Check if game session expired (not token, just game session)
                        page_source = driver.page_source
                        if "YOUR GAME SESSION EXPIRED" in page_source or "RELOAD THE GAME" in page_source:
                            log_msg("⚠️  Game session expired - Auto-reloading game...")
                            driver.get(GAME_URL)
                            time.sleep(5)
                            continue
                            
                    except Exception as e:
                        bot_state["failed_load_count"] += 1
                        log_msg(f"⚠️  Screenshot timeout: {str(e)[:30]}")
                        
                        if bot_state["failed_load_count"] > 5:
                            if not bot_state["session_expired_alert_sent"]:
                                error_msg = "🔴 TOKEN EXPIRED - Restarting bot session..."
                                log_msg(error_msg)
                                send_telegram_message(f"{error_msg}\n⏱️ Time: {eth_time()}")
                                bot_state["session_expired_alert_sent"] = True
                            break
                        
                        time.sleep(1)
                        continue
                    
                    scan_count += 1
                    is_results = is_results_phase(img_path)
                    
                    if is_results:
                        if not in_results_phase:
                            log_msg("⏸️  RESULTS PHASE (Top 20 - No alerts)")
                            in_results_phase = True
                    else:
                        if in_results_phase:
                            log_msg("⏱️  COUNTDOWN PHASE RESUMED")
                            in_results_phase = False
                        
                        if detect_green_flash(img_path):
                            bot_state["flashes_detected"] += 1
                            bot_state["daily_flashes"] += 1
                            
                            alert_caption = f"🟢 GREEN FLASH #{bot_state['daily_flashes']} | Time: {eth_time()}"
                            if send_to_telegram(img_path, alert_caption):
                                log_msg(f"🚨 GREEN FLASH #{bot_state['daily_flashes']} DETECTED & SENT!")
                            
                            time.sleep(0.5)
                    
                    elapsed = time.time() - bot_state["session_start"]
                    
                    if time.time() - last_status_log > 30:
                        log_msg(f"✅ ACTIVE | Scans: {scan_count} | Today: {bot_state['daily_flashes']} flashes | Time: {eth_time()}")
                        last_status_log = time.time()
                    
                    if time.time() - last_heartbeat_log > 10:
                        log_msg(f"❤️  HEARTBEAT | Bot running 24/7 | {eth_time()}")
                        last_heartbeat_log = time.time()
                    
                    if time.time() - last_daily_report > 86400:
                        report_msg = f"📊 24-HOUR REPORT\n📅 Date: {eth_date()}\n🟢 Flashes: {bot_state['daily_flashes']}\n⏱️ Time: {eth_time()}"
                        if send_telegram_message(report_msg):
                            log_msg(f"📊 24-hour report sent: {bot_state['daily_flashes']} flashes")
                        bot_state["daily_flashes"] = 0
                        last_daily_report = time.time()
                    
                    time.sleep(1)
                    
                except Exception as e:
                    log_msg(f"⚠️  Scan error: {str(e)[:50]}")
                    time.sleep(1)
            
            log_msg(f"✅ Session #{session_retry} complete - {bot_state['flashes_detected']} total flashes")
            
        except Exception as e:
            log_msg(f"❌ Session error: {str(e)[:50]}")
        
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            
            bot_state["driver"] = None
            log_msg("⏳ Restarting in 10 seconds...")
            time.sleep(10)

def main():
    start_web_server()
    
    command_thread = threading.Thread(target=handle_telegram_commands, daemon=True)
    command_thread.start()
    log_msg("✅ Telegram command listener started")
    
    monitor_game()

if __name__ == "__main__":
    main()
