import json
import time
from datetime import timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from backend.db.session import SessionLocal
from backend.db.models import User
from backend.core.security import create_access_token

def get_test_user():
    db = SessionLocal()
    user = db.query(User).filter(User.is_verified == True, User.onboarding_completed == True).first()
    db.close()
    return user

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    return webdriver.Chrome(options=chrome_options)

def verify_issue_1_geolocation():
    print("\n" + "="*70)
    print("VERIFYING ISSUE 1: Geolocation retry loop, exponential backoff & cap")
    print("="*70)
    user = get_test_user()
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})

    driver = create_driver()
    try:
        driver.execute_cdp_cmd("Browser.grantPermissions", {
            "origin": "http://127.0.0.1:8000",
            "permissions": ["geolocation"]
        })
        driver.get("http://127.0.0.1:8000/")
        driver.execute_script("""
            localStorage.setItem('weathergpt_api_base', '/api/v1');
            localStorage.setItem('weathergpt_auth_token', arguments[0]);
            localStorage.setItem('skyzen_loc_permission_status', 'granted');
        """, token)

        # Inject intercepted geolocation to simulate timeout
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                window.geoCallCount = 0;
                if (navigator.permissions && navigator.permissions.query) {
                    const origQuery = navigator.permissions.query;
                    navigator.permissions.query = function(p) {
                        if (p && p.name === 'geolocation') {
                            return Promise.resolve({ state: 'granted' });
                        }
                        return origQuery.apply(this, arguments);
                    };
                }
                navigator.geolocation.getCurrentPosition = function(success, error, options) {
                    window.geoCallCount++;
                    const callId = window.geoCallCount;
                    console.log("[TestHarness] getCurrentPosition invoked (#" + callId + ")");
                    setTimeout(() => {
                        if (error) {
                            error({ code: 3, message: "Timeout expired" });
                        }
                    }, 50);
                };
            """
        })

        driver.get("http://127.0.0.1:8000/")
        time.sleep(2)

        # Simulate repeated window focus events immediately (should be throttled/backed off)
        for i in range(3):
            time.sleep(0.3)
            driver.execute_script("""
                console.log('[TestHarness] Rapid window focus event #' + arguments[0]);
                window.dispatchEvent(new Event('focus'));
            """, i + 1)

        # Check call count: should NOT have retried 4 times; must be throttled
        geo_calls = driver.execute_script("return window.geoCallCount;")
        print(f"Total getCurrentPosition calls made during backoff: {geo_calls} (Target: 1, suppressed by backoff)")
        assert geo_calls == 1, f"Expected exactly 1 call before backoff, got {geo_calls}"

        # Now simulate reaching failure cap (3 failures)
        driver.execute_script("""
            geoConsecutiveFailures = 3;
            geoBackoffUntil = Date.now() + 45000;
            console.log('[TestHarness] Simulating window focus when max failures reached (3/3)');
            window.dispatchEvent(new Event('focus'));
        """)
        time.sleep(0.5)

        # Assert no new calls were made
        geo_calls_after_cap = driver.execute_script("return window.geoCallCount;")
        print(f"Total calls after failure cap reached: {geo_calls_after_cap} (Strictly halted)")
        assert geo_calls_after_cap == 1, "Calls must be completely halted when failure cap is reached"

        # Now simulate manual user click on GPS button: must reset counters
        driver.execute_script("""
            console.log('[TestHarness] Simulating manual user click on geoBtn');
            const btn = document.getElementById('geoBtn');
            if (btn) btn.click();
        """)
        time.sleep(0.5)

        geo_calls_after_click = driver.execute_script("return window.geoCallCount;")
        print(f"Total calls after manual user click: {geo_calls_after_click} (Manual retry successfully executed)")
        assert geo_calls_after_click == 2, "Manual click must reset failure cap and trigger fresh attempt"

        logs = driver.get_log("browser")
        print("\nCaptured Browser Console Logs for Issue 1:")
        for entry in logs:
            msg = entry['message']
            if any(k in msg for k in ['[Location]', '[TestHarness]', 'Geolocation error', 'throttled', 'Timeout']):
                print(f"  [{entry['level']}] {msg}")

        print("ISSUE 1 VERIFICATION PASSED: No loop, exponential backoff active, max-retry cap halts retries, user click resets.")
    finally:
        driver.quit()

def verify_issue_2_session_restore():
    print("\n" + "="*70)
    print("VERIFYING ISSUE 2: Session restore & proactive / resilient token renewal")
    print("="*70)
    user = get_test_user()
    
    # 1. Test fresh active login session restore
    valid_token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})

    driver = create_driver()
    try:
        driver.get("http://127.0.0.1:8000/")
        driver.execute_script("""
            localStorage.setItem('weathergpt_api_base', '/api/v1');
            localStorage.setItem('weathergpt_auth_token', arguments[0]);
            localStorage.setItem('skyzen_loc_permission_status', 'granted');
        """, valid_token)

        # Reload tab
        driver.get("http://127.0.0.1:8000/")
        time.sleep(2)

        # Check authenticated state in DOM
        is_auth = driver.execute_script("return typeof currentUser !== 'undefined' && currentUser !== null && currentUser.id === arguments[0];", str(user.id))
        print(f"Session restored on fresh reopen: {is_auth}")
        assert is_auth, "Valid session must restore successfully on app reopen"

        # Check console logs for absence of 401 / session expired
        logs = driver.get_log("browser")
        error_logs = [l['message'] for l in logs if '401' in l['message'] or 'Session restore failed' in l['message']]
        print(f"Unexpected 401 / session expired errors on valid reopen: {error_logs}")
        assert len(error_logs) == 0, f"No 401 or session expired warnings expected: {error_logs}"

        # 2. Test expired token renewal via resilient /auth/refresh
        expired_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role},
            expires_delta=timedelta(seconds=-60) # Expired 1 minute ago (within 7-day grace period)
        )
        driver.execute_script("""
            localStorage.setItem('weathergpt_auth_token', arguments[0]);
            console.log('[TestHarness] Replaced token with expired token within grace period');
        """, expired_token)

        # Reload tab
        driver.get("http://127.0.0.1:8000/")
        time.sleep(3)

        # Verify session was renewed and user is still authenticated!
        is_still_auth = driver.execute_script("return typeof currentUser !== 'undefined' && currentUser !== null && currentUser.id === arguments[0];", str(user.id))
        new_token = driver.execute_script("return window.apiClient.getToken();")
        print(f"Session renewed after expired token: {is_still_auth}")
        print(f"Fresh token received: {new_token != expired_token}")
        assert is_still_auth, "Recently expired session within grace period must be renewed"
        assert new_token != expired_token, "Token must be replaced with fresh access token"

        logs_renew = driver.get_log("browser")
        print("\nCaptured Browser Console Logs for Issue 2:")
        for entry in logs_renew:
            msg = entry['message']
            if any(k in msg for k in ['[Auth]', '[TestHarness]', 'session', 'renewal', 'token']):
                print(f"  [{entry['level']}] {msg}")

        print("ISSUE 2 VERIFICATION PASSED: No false session expiry, seamless token renewal, valid session preserved.")
    finally:
        driver.quit()

if __name__ == "__main__":
    verify_issue_1_geolocation()
    verify_issue_2_session_restore()
