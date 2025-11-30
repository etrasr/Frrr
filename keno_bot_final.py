#!/usr/bin/env python3
"""
KENO BOT v3 - GREEN FLASH DETECTION (24/7)
NO DATABASE - Just Telegram alerts
OPTIMIZED: Better error handling & timeouts
"""
import time
import requests
import os
import subprocess
from datetime import datetime, timedelta, timezone
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth

ETHIOPIA_TZ = timezone(timedelta(hours=3))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SESSION_TOKEN = os.environ.get("SESSION_TOKEN")
GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"
BASE_URL = "https://flashsport.bet"

def eth_time():
    return datetime.now(ETHIOPIA_TZ).strftime("%H:%M:%S")

def log_msg(msg):
    ts = eth_time()
    print(f"[{ts}] {msg}", flush=True)

def send_to_telegram(image_path, caption):
    """Send screenshot to Telegram"""
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

def count_green_pixels(image_path):
    """Count green pixels in image"""
    try:
        img = Image.open(image_path).convert('RGB')
        pixels = img.load()
        width, height = img.size
        
        green_count = 0
        
        # Sample pixels efficiently - every 3rd pixel (faster)
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
    """Detect single/few green numbers (50-300 pixels)"""
    green_count = count_green_pixels(image_path)
    
    # Single/few numbers = 50-300 pixels
    # Results (20 numbers) = 300+ pixels
    if 50 < green_count < 300:
        return True
    
    return False

def is_results_phase(image_path):
    """Detect results phase (20 drawn numbers - 300+ green pixels)"""
    green_count = count_green_pixels(image_path)
    return green_count > 300

def setup_chrome():
    """Setup Chrome browser with better error handling"""
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

def main():
    log_msg("=" * 70)
    log_msg("🟢 KENO BOT v3 - GREEN FLASH DETECTION (24/7)")
    log_msg("=" * 70)
    log_msg("🔴 TELEGRAM ALERTS ONLY - No database")
    log_msg("🔴 Countdown Phase (60→0): Green flashes detected")
    
    session_retry = 0
    
    while True:
        driver = None
        try:
            session_retry += 1
            log_msg(f"📍 Session #{session_retry}")
            
            # Setup browser
            driver = setup_chrome()
            
            # Login
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
            
            # Load game
            log_msg("🎮 Loading game...")
            driver.get(GAME_URL)
            time.sleep(5)
            
            log_msg("⏱️  COUNTDOWN PHASE - Monitoring for green flashes")
            
            # Main monitoring loop
            session_start = time.time()
            flashes_detected = 0
            status_sent = False
            in_results_phase = False
            
            while (time.time() - session_start) < 1800:  # 30 min session
                try:
                    img_path = f"/tmp/keno_scan_{int(time.time() * 100)}.png"
                    
                    # Timeout for screenshot
                    try:
                        driver.save_screenshot(img_path)
                    except Exception as e:
                        log_msg(f"⚠️  Screenshot timeout: {str(e)[:30]}")
                        time.sleep(1)
                        continue
                    
                    # Check current phase
                    is_results = is_results_phase(img_path)
                    
                    if is_results:
                        # Results phase (IGNORE)
                        if not in_results_phase:
                            log_msg("⏸️  RESULTS PHASE (Top 20 - No alerts)")
                            in_results_phase = True
                    else:
                        # Countdown phase (DETECT)
                        if in_results_phase:
                            log_msg("⏱️  COUNTDOWN PHASE RESUMED")
                            in_results_phase = False
                        
                        # Check for green flash
                        if detect_green_flash(img_path):
                            flashes_detected += 1
                            
                            # ALERT
                            alert_caption = f"🟢 GREEN FLASH #{flashes_detected} | Time: {eth_time()}"
                            if send_to_telegram(img_path, alert_caption):
                                log_msg(f"🚨 GREEN FLASH #{flashes_detected} DETECTED & SENT!")
                            
                            time.sleep(0.5)
                    
                    # STATUS UPDATE EVERY 2 HOURS
                    elapsed = time.time() - session_start
                    if elapsed > 7200 and not status_sent:
                        try:
                            status_img = f"/tmp/keno_status_{int(time.time())}.png"
                            driver.save_screenshot(status_img)
                            caption = f"✅ BOT ALIVE | Flashes: {flashes_detected} | Time: {eth_time()}"
                            if send_to_telegram(status_img, caption):
                                log_msg(f"📸 Status sent: {flashes_detected} flashes in 2 hours")
                            status_sent = True
                        except Exception as e:
                            log_msg(f"❌ Status error: {str(e)[:50]}")
                    
                    time.sleep(1)
                    
                except Exception as e:
                    log_msg(f"⚠️  Scan error: {str(e)[:50]}")
                    time.sleep(1)
            
            log_msg(f"✅ Session #{session_retry} complete - {flashes_detected} flashes")
            
        except Exception as e:
            log_msg(f"❌ Session error: {str(e)[:50]}")
        
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            
            log_msg("⏳ Restarting in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    main()
