import time
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LOGIN_PHONE = os.environ.get("LOGIN_PHONE")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD")

# Direct link to game
GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"

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
    # Using a modern Desktop User Agent to avoid Mobile Overlay issues
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ.get("CHROME_BIN")
    
    return webdriver.Chrome(options=chrome_options)

def angular_input(driver, element, value):
    """
    This function forces Angular to recognize that we typed something.
    Standard Selenium .send_keys() often fails on sites like this.
    """
    driver.execute_script("""
        var elem = arguments[0];
        var value = arguments[1];
        elem.value = value;
        elem.dispatchEvent(new Event('input', { bubbles: true }));
        elem.dispatchEvent(new Event('change', { bubbles: true }));
        elem.dispatchEvent(new Event('blur', { bubbles: true }));
    """, element, value)

def perform_login(driver):
    print("🔑 Logic: Angular Injection Mode")
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 1. Find the Phone Input (using the specific attributes seen in your logs)
        print("   - Finding Phone Input...")
        phone_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[formcontrolname='login']")))
        
        # 2. Inject Phone Number (Angular Safe Way)
        angular_input(driver, phone_input, LOGIN_PHONE)
        print(f"   - Phone injected ({LOGIN_PHONE}).")
        time.sleep(1)
        
        # 3. Find Password Input
        print("   - Finding Password Input...")
        pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        
        # 4. Inject Password (Angular Safe Way)
        angular_input(driver, pass_input, LOGIN_PASSWORD)
        print("   - Password injected.")
        time.sleep(1)
        
        # 5. NUCLEAR OPTION: Submit the Form Directly
        # We don't click the button. We find the <form> and force the browser to submit it.
        print("   - Force-Submitting the Form...")
        try:
            form = driver.find_element(By.TAG_NAME, "form")
            driver.execute_script("arguments[0].submit();", form)
        except Exception as e:
            print(f"   - Form submit failed ({e}), trying button click as backup...")
            # Backup: Click the login button if form submit fails
            btn = driver.find_element(By.XPATH, "//*[contains(text(), 'LOGIN')]")
            driver.execute_script("arguments[0].click();", btn)

        # 6. Wait for URL Change
        print("   - Waiting for Redirect (Max 20s)...")
        time.sleep(5)
        
        # Check loops to see if we moved
        for i in range(15):
            if "auth" not in driver.current_url and "Sign" not in driver.title:
                print(f"   - ✅ Success! We left the login page. Current Title: {driver.title}")
                return True
            time.sleep(1)
            
        print("❌ Login timed out. Still on login page.")
        
        # Check for error text
        body = driver.find_element(By.TAG_NAME, "body").text
        if "Invalid" in body or "Incorrect" in body:
            send_telegram(f"❌ Login Credential Error. The site says your Phone/Pass is wrong.")
        else:
            send_telegram(f"❌ Login Stuck. We are at: {driver.current_url}")
            
        return False
        
    except Exception as e:
        print(f"❌ Logic Crash: {e}")
        return False

def find_game_grid(driver):
    print("🔎 Scanning for Keno grid...")
    
    # 1. Check Main Page
    cls = detect_grid_logic(driver)
    if cls: return cls

    # 2. Check Iframes
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"  - Found {len(frames)} frames. Checking inside them...")
    
    for i, frame in enumerate(frames):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            cls = detect_grid_logic(driver)
            if cls:
                print(f"✅ FOUND GAME inside Frame #{i+1}!")
                return cls
        except:
            continue
            
    return None

def detect_grid_logic(driver):
    try:
        # Search for text '80'
        potential_80s = driver.find_elements(By.XPATH, "//*[text()='80']")
        for el in potential_80s:
            class_name = el.get_attribute("class")
            if not class_name: continue
            base_class = class_name.split()[0]
            siblings = driver.find_elements(By.CLASS_NAME, base_class)
            if 70 <= len(siblings) <= 90:
                return base_class
    except:
        pass
    return None

def main():
    if not LOGIN_PHONE or not LOGIN_PASSWORD:
        print("❌ Error: Missing credentials.")
        return

    driver = setup_driver()
    print("🚀 Bot Started (Angular Injection Mode)...")
    
    try:
        driver.get(GAME_URL)
        time.sleep(5)
        
        # LOGIN CHECK
        if "Sign" in driver.title or "auth" in driver.current_url:
            success = perform_login(driver)
            if not success:
                driver.quit()
                return
            
            # Navigate explicitly to game again to be safe
            driver.get(GAME_URL)
            time.sleep(15)

        # FIND GRID
        keno_class = find_game_grid(driver)
        
        if not keno_class:
            send_telegram(f"❌ Login worked, but cannot find numbers. Title: {driver.title}")
            return

        msg = f"✅ LOCKED ON! Tracking via class: '{keno_class}'"
        print(msg)
        send_telegram(msg)
        
        last_alert_numbers = []
        
        while True:
            script = f"""
            var changed_numbers = [];
            var elements = document.getElementsByClassName('{keno_class}');
            for (var i = 0; i < elements.length; i++) {{
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
                    if active_numbers != last_alert_numbers:
                        clean_nums = [n for n in active_numbers if n.strip().isdigit()]
                        if clean_nums:
                            alert_msg = f"⚡ FLASH: {', '.join(clean_nums)}"
                            print(alert_msg)
                            send_telegram(alert_msg)
                            last_alert_numbers = active_numbers
            except:
                break
            time.sleep(0.1)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
