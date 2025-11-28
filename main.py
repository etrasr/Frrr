import time
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
# Using the direct link you provided
URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"

def send_telegram(message):
    print(f"🔔 {message}")
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": message})
        except:
            pass

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Simulate a Mobile Phone so the site loads the mobile version you see
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ.get("CHROME_BIN")
    
    return webdriver.Chrome(options=chrome_options)

def find_game_grid(driver):
    """
    1. Checks the main page.
    2. Checks inside iframes (embedded windows).
    3. Returns the HTML Class Name of the numbers if found.
    """
    print("🔎 Scanning for Keno grid (Numbers 1-80)...")
    
    # 1. Check Main Page First
    cls = detect_grid_logic(driver)
    if cls: return cls

    # 2. Check Iframes (Most likely here)
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"  - Found {len(frames)} frames. Checking inside them...")
    
    for i, frame in enumerate(frames):
        try:
            driver.switch_to.default_content() # Reset
            driver.switch_to.frame(frame)      # Jump inside the box
            
            cls = detect_grid_logic(driver)
            if cls:
                print(f"✅ FOUND GAME inside Frame #{i+1}!")
                return cls
        except:
            continue

    return None

def detect_grid_logic(driver):
    """
    Helper function: Looks for the number '80' and checks if it's part of a large grid.
    """
    try:
        # Find elements that contain the text '80'
        potential_80s = driver.find_elements(By.XPATH, "//*[text()='80']")
        
        for el in potential_80s:
            class_name = el.get_attribute("class")
            if not class_name: continue
            
            base_class = class_name.split()[0]
            
            # Verify if this is a grid (should have ~80 items)
            siblings = driver.find_elements(By.CLASS_NAME, base_class)
            count = len(siblings)
            
            if 70 <= count <= 90:
                print(f"    -> Identified Grid. Class: '{base_class}' (Count: {count})")
                return base_class
    except:
        pass
    return None

def main():
    driver = setup_driver()
    print("🚀 Bot Started (Direct Link Mode)...")
    
    try:
        driver.get(URL)
        time.sleep(10) # Wait for loading
        
        # Locate the numbers
        keno_class = find_game_grid(driver)
        
        if not keno_class:
            send_telegram(f"❌ Failed to find numbers. Page title: {driver.title}")
            return

        msg = f"✅ LOCK ON! Tracking numbers with class: '{keno_class}'"
        print(msg)
        send_telegram(msg)
        
        # Monitor Loop
        last_alert_numbers = []
        
        while True:
            # JavaScript: Find elements with EXTRA classes (meaning they changed color)
            script = f"""
            var changed_numbers = [];
            var elements = document.getElementsByClassName('{keno_class}');
            for (var i = 0; i < elements.length; i++) {{
                // If the class string is longer, it has a modifier (like 'active' or 'green')
                if (elements[i].className.length > '{keno_class}'.length + 2) {{
                    changed_numbers.push(elements[i].innerText);
                }}
            }}
            return changed_numbers;
            """
            
            try:
                active_numbers = driver.execute_script(script)
                
                if active_numbers:
                    active_numbers.sort()
                    # If this is a new flash we haven't seen yet
                    if active_numbers != last_alert_numbers:
                        # Filter out empty text
                        clean_nums = [n for n in active_numbers if n.strip().isdigit()]
                        
                        if clean_nums:
                            alert_msg = f"⚡ FLASH: {', '.join(clean_nums)}"
                            print(alert_msg)
                            send_telegram(alert_msg)
                            last_alert_numbers = active_numbers
            except Exception as e:
                print(f"Loop Warning: {e}")
                break # If frame crashes, restart logic could be added here
                
            time.sleep(0.1) # Scan fast
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
