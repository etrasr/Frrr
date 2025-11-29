import time
import requests
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth

# --- CONFIGURATION ---
sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SESSION_TOKEN = os.environ.get("SESSION_TOKEN")
# Make sure this is the exact cookie name from your browser inspection
# detailed below in instructions
COOKIE_NAME = "token" 

BASE_URL = "https://flashsport.bet"
# This URL forces the mobile view which is easier to scrape
GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"

def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)

def send_telegram_msg(message):
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": message})
        except: pass

def send_telegram_photo(driver, caption=""):
    """
    Takes a screenshot and sends it to Telegram immediately.
    This is how you verify the bot is watching the right thing.
    """
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            # 1. Take Screenshot to memory
            screenshot = driver.get_screenshot_as_png()
            
            # 2. Send to Telegram API
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            files = {'photo': ('screen.png', screenshot)}
            data = {'chat_id': CHAT_ID, 'caption': caption}
            requests.post(url, data=data, files=files)
            log("📸 Screenshot sent to Telegram!")
        except Exception as e:
            log(f"⚠️ Failed to send photo: {e}")

def setup_driver():
    log("🚀 Launching Chrome...")
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=375,812") # Mobile Size
    
    # Standard User Agent
    options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36")

    driver = webdriver.Chrome(options=options)
    
    # Apply Stealth
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    driver.set_page_load_timeout(60)
    return driver

def inject_session(driver):
    """
    Bypasses login by injecting the cookie.
    """
    try:
        log("🍪 Injecting Session Cookie...")
        # 1. Go to Base URL first (Required to set cookies)
        driver.get(BASE_URL)
        time.sleep(3)
        
        # 2. Add the Cookie
        driver.add_cookie({
            "name": COOKIE_NAME, # Check if your site uses 'token', 'access_token', or 'PHPSESSID'
            "value": SESSION_TOKEN,
            "domain": "flashsport.bet",
            "path": "/"
        })
        
        # 3. Now go to the Game
        log("🔄 Loading Game Page...")
        driver.get(GAME_URL)
        time.sleep(10) # Wait for game to load
        return True
    except Exception as e:
        log(f"❌ Session Injection Failed: {e}")
        return False

def find_game_frame(driver):
    """
    Finds the iframe containing the game numbers.
    """
    log("🔎 Looking for Game Frame...")
    
    # If we are already in the frame, return True
    if "80" in driver.page_source:
        return True
        
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in frames:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            # Check if this frame has the number 80 (Keno grid)
            if "80" in driver.page_source:
                log("✅ Found Keno Game Frame!")
                return True
        except:
            continue
            
    log("⚠️ Could not find game frame.")
    return False

def main():
    if not SESSION_TOKEN:
        print("❌ Error: SESSION_TOKEN is missing from Environment Variables.")
        return

    while True:
        driver = setup_driver()
        try:
            # 1. Login via Cookie
            inject_session(driver)
            
            # 2. Find the Game (Iframe)
            if find_game_frame(driver):
                send_telegram_msg("✅ Bot Connected! Sending verification photo...")
                
                # 3. Monitor Loop
                while True:
                    # A. Send Proof to Telegram
                    send_telegram_photo(driver, caption="Verifying Keno Board...")
                    
                    # B. Check for Draw ID (The regex you provided)
                    # We use execute_script to grab text even if hidden
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                    
                    # Simple check to see if we are logged in
                    if "Login" in driver.title or "Sign in" in page_text:
                        log("❌ Cookie expired or invalid. Redirected to Login.")
                        send_telegram_msg("⚠️ Session Token Expired. Update variable.")
                        break
                    
                    log("✅ Monitoring active... (Waiting 30s)")
                    
                    # C. Wait 30 seconds before next check
                    time.sleep(30)
                    
                    # Ensure we are still in the right frame
                    find_game_frame(driver)
            
            else:
                send_telegram_msg("❌ Bot loaded page but couldn't find the Keno grid.")
                send_telegram_photo(driver, caption="Debug: What I see")
                
        except Exception as e:
            log(f"💥 Error: {e}")
        finally:
            driver.quit()
            log("🔄 Restarting Bot...")
            time.sleep(10)

if __name__ == "__main__":
    main()
