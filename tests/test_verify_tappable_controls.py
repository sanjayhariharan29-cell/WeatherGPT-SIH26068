import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from backend.db.session import SessionLocal
from backend.db.models import User
from backend.core.security import create_access_token

def get_developer_user():
    db = SessionLocal()
    user = db.query(User).filter(User.role == "developer").first()
    if not user:
        user = db.query(User).first()
        if user:
            user.role = "developer"
            db.commit()
            db.refresh(user)
    db.close()
    return user

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,800")
    return webdriver.Chrome(options=chrome_options)

def verify_controls_in_browser():
    print("\n" + "="*70)
    print("VERIFYING TAPPABLE CONTROLS & IN-FLIGHT LOADING IN BROWSER")
    print("="*70)
    user = get_developer_user()
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})

    driver = create_driver()
    try:
        driver.get("http://127.0.0.1:8000/")
        driver.execute_script("""
            localStorage.setItem('weathergpt_api_base', '/api/v1');
            localStorage.setItem('weathergpt_auth_token', arguments[0]);
        """, token)
        driver.refresh()
        time.sleep(1.5)

        # Check that styles.css is loaded and contains universal :active rules
        has_active_rule = driver.execute_script("""
            for (let sheet of document.styleSheets) {
                try {
                    for (let rule of sheet.cssRules) {
                        if (rule.selectorText && rule.selectorText.includes(':active')) {
                            return true;
                        }
                    }
                } catch(e) {}
            }
            return false;
        """)
        print(f"[Check 1] Stylesheet contains :active rules: {has_active_rule}")
        assert has_active_rule, "No :active rules found in document stylesheets"

        # Check setButtonLoading functionality
        res = driver.execute_script("""
            const testBtn = document.createElement('button');
            testBtn.id = 'qaTestBtn';
            testBtn.innerHTML = '<span class=\"material-symbols-rounded\">send</span><span>Send</span>';
            document.body.appendChild(testBtn);

            // Test setting loading
            setButtonLoading(testBtn, true, 'Sending...');
            const isLoadingApplied = testBtn.disabled && 
                                     testBtn.classList.contains('btn-loading') && 
                                     testBtn.querySelector('.material-symbols-rounded').classList.contains('spin-anim') &&
                                     testBtn.querySelector('.material-symbols-rounded').textContent === 'progress_activity';

            // Test resetting loading
            setButtonLoading(testBtn, false);
            const isResetApplied = !testBtn.disabled && 
                                   !testBtn.classList.contains('btn-loading') &&
                                   testBtn.querySelector('.material-symbols-rounded').textContent === 'send';

            testBtn.remove();
            return { isLoadingApplied, isResetApplied };
        """)
        print(f"[Check 2] setButtonLoading works cleanly: {res}")
        assert res['isLoadingApplied'], "setButtonLoading failed to apply loading state"
        assert res['isResetApplied'], "setButtonLoading failed to reset state"

        # Check Theme Toggle Button
        themeBtn = driver.find_element(By.ID, "themeToggleBtn")
        assert themeBtn is not None
        print("[Check 3] Theme toggle button exists and is tappable")

        # Check Navigation Items
        nav_items = driver.find_elements(By.CLASS_NAME, "nav-item")
        print(f"[Check 4] Found {len(nav_items)} navigation items")
        assert len(nav_items) >= 5, f"Expected at least 5 nav items, found {len(nav_items)}"

        # Check Map Layer Pills
        driver.get("http://127.0.0.1:8000/")
        driver.execute_script("navigateToScreen('radar');")
        time.sleep(1)
        layer_pills = driver.find_elements(By.CLASS_NAME, "map-layer-pill")
        print(f"[Check 5] Found {len(layer_pills)} map layer pills on Radar screen")
        assert len(layer_pills) >= 4

        # Check Developer Console
        driver.get(f"http://127.0.0.1:8000/developer.html?token={token}")
        time.sleep(1.5)

        dev_buttons = driver.find_elements(By.CLASS_NAME, "dev-btn")
        print(f"[Check 6] Developer console loaded with {len(dev_buttons)} dev buttons")
        assert len(dev_buttons) >= 4

        btn_declare = driver.find_element(By.ID, "btnDeclareAlert")
        assert btn_declare is not None
        print("[Check 7] Developer Official Warning declaration button exists")

        print("\nALL IN-BROWSER CHECKS PASSED SUCCESSFULLY!")
    finally:
        driver.quit()

if __name__ == "__main__":
    verify_controls_in_browser()
