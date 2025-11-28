import time
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- SECURITY UPDATE ---
# We now get these values from Render's Environment Variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
URL = "https://flashsport.bet/"

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Error: Telegram credentials not found in Environment Variables.")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, data=data)
        print(f"Sent: {message}")
    except Exception as e:
        print(f"Failed to send: {e}")

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # If we are on Render, we need to point to the installed Chrome binary
    # We will set a "CHROME_BIN" variable in Render as well just to be safe
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ.get("CHROME_BIN")
    
    # Use Webdriver Manager to install the driver automatically
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def find_keno_class(driver):
    """
    Auto-detects the Keno grid by looking for the number '80'
    and checking if it belongs to a large group of similar elements.
    """
    print("Scanning page for Keno grid...")
    
    # Search for any element containing the text '80'
    potential_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '80')]")
    
    for el in potential_elements:
        try:
            class_name = el.get_attribute("class")
            if not class_name:
                continue
            
            # Identify the FIRST class name (main class)
            base_class = class_name.split()[0]
            
            # Count how many other elements have this same class
            siblings = driver.find_elements(By.CLASS_NAME, base_class)
            count = len(siblings)
            
            # A Keno board usually has 80 numbers (allow range 75-85)
            if 75 <= count <= 85:
                print(f"✅ FOUND GRID! Class Name: '{base_class}' (Count: {count})")
                return base_class
        except:
            continue
            
    return None

def main():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ CRITICAL ERROR: You forgot to add TELEGRAM_TOKEN or CHAT_ID in Render settings!")
        return

    try:
        driver = setup_driver()
        print("Bot Starting...")
        driver.get(URL)
        time.sleep(15) # Wait longer for the site to fully load
        
        # 1. Auto-Detect the Grid
        keno_class = find_keno_class(driver)
        
        if not keno_class:
            send_telegram("❌ Could not find the Keno grid automatically. The site might be blocking us or the structure changed.")
            driver.quit()
            return

        msg = f"Bot connected! Tracking Keno grid via class: {keno_class}"
        print(msg)
        send_telegram(msg)
        
        # 2. Monitor Loop
        last_alert_numbers = []
        
        while True:
            # JavaScript Logic:
            # "Find all elements with the keno class. 
            # If an element has MORE classes than just the base class (e.g., 'keno-ball active'), get its text."
            script = f"""
            var changed_numbers = [];
            var elements = document.getElementsByClassName('{keno_class}');
            for (var i = 0; i < elements.length; i++) {{
                // Compare current class string length vs original base class length
                // If it's longer, it means a modifier class (like 'green' or 'flash') was added.
                if (elements[i].className.length > '{keno_class}'.length) {{
                    changed_numbers.push(elements[i].innerText);
                }}
            }}
            return changed_numbers;
            """
            
            try:
                active_numbers = driver.execute_script(script)
                
                # Check if we found numbers and if they are different from the last alert
                if active_numbers:
                    # Sort them to make comparison consistent
                    active_numbers.sort()
                    
                    if active_numbers != last_alert_numbers:
                        clean_nums = [n for n in active_numbers if n.strip() != ""]
                        if clean_nums:
                            alert_msg = f"⚡ FLASH: {', '.join(clean_nums)}"
                            print(alert_msg)
                            send_telegram(alert_msg)
                            last_alert_numbers = active_numbers
            except Exception as e:
                print(f"Loop error: {e}")

            # Check fast
            time.sleep(0.2)
            
    except Exception as e:
        print(f"Crashed: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
