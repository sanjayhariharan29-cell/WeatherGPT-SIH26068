import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from backend.db.session import SessionLocal
from backend.db.models import User
from backend.core.security import create_access_token

def get_test_token():
    db = SessionLocal()
    user = db.query(User).filter(User.email == "test_perf@weathergpt.in").first()
    return create_access_token(data={"sub": str(user.id)})

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return webdriver.Chrome(options=chrome_options)

def run_test_granted():
    token = get_test_token()
    driver = create_driver()
    try:
        driver.execute_cdp_cmd("Browser.grantPermissions", {
            "origin": "http://127.0.0.1:8000",
            "permissions": ["geolocation"]
        })
        driver.execute_cdp_cmd("Emulation.setGeolocationOverride", {
            "latitude": 11.0168,
            "longitude": 76.9558,
            "accuracy": 15
        })

        driver.get("http://127.0.0.1:8000/")
        driver.execute_script("""
            localStorage.setItem('weathergpt_api_base', 'http://127.0.0.1:8000/api/v1');
            localStorage.setItem('weathergpt_auth_token', arguments[0]);
            localStorage.setItem('skyzen_loc_permission_status', 'granted');
            localStorage.setItem('skyzen_last_known_location', JSON.stringify({
                name: 'Coimbatore',
                latitude: 11.0168,
                longitude: 76.9558,
                accuracy: 15,
                timestamp: new Date().toISOString(),
                source: 'live_gps'
            }));
        """, token)

        driver.get_log("performance")
        driver.get("http://127.0.0.1:8000/")
        time.sleep(5)

        logs = driver.get_log("performance")
        requests = []
        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                if msg["method"] == "Network.requestWillBeSent":
                    url = msg["params"]["request"]["url"]
                    method = msg["params"]["request"]["method"]
                    if method != "OPTIONS":
                        requests.append((method, url))
            except Exception:
                pass

        counts = {}
        for m, u in requests:
            for target in ["alerts", "air-quality", "preferences", "reverse"]:
                if target in u:
                    counts[target] = counts.get(target, 0) + 1

        return requests, counts
    finally:
        driver.quit()

def run_test_denied():
    token = get_test_token()
    driver = create_driver()
    try:
        driver.get("http://127.0.0.1:8000/")
        driver.execute_script("""
            localStorage.setItem('weathergpt_api_base', 'http://127.0.0.1:8000/api/v1');
            localStorage.setItem('weathergpt_auth_token', arguments[0]);
            localStorage.setItem('skyzen_loc_permission_status', 'denied');
            localStorage.setItem('skyzen_loc_prompt_dismissed', 'true');
            localStorage.setItem('skyzen_last_known_location', JSON.stringify({
                name: 'Coimbatore',
                latitude: 11.0168,
                longitude: 76.9558,
                accuracy: 15,
                timestamp: new Date().toISOString(),
                source: 'manual'
            }));
        """, token)

        driver.get_log("performance")
        driver.get("http://127.0.0.1:8000/")
        time.sleep(5)

        logs = driver.get_log("performance")
        requests = []
        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                if msg["method"] == "Network.requestWillBeSent":
                    url = msg["params"]["request"]["url"]
                    method = msg["params"]["request"]["method"]
                    if method != "OPTIONS":
                        requests.append((method, url))
            except Exception:
                pass

        counts = {}
        for m, u in requests:
            for target in ["alerts", "air-quality", "preferences", "reverse"]:
                if target in u:
                    counts[target] = counts.get(target, 0) + 1

        return requests, counts
    finally:
        driver.quit()

def run_in_flight_dedup_test():
    token = get_test_token()
    driver = create_driver()
    try:
        driver.get("http://127.0.0.1:8000/")
        driver.execute_script("""
            localStorage.setItem('weathergpt_api_base', 'http://127.0.0.1:8000/api/v1');
            localStorage.setItem('weathergpt_auth_token', arguments[0]);
            if (window.apiClient) {
                window.apiClient.setBaseUrl('http://127.0.0.1:8000/api/v1');
                window.apiClient.setToken(arguments[0]);
                window.apiClient.clearCache();
            }
        """, token)

        driver.get_log("performance")

        # Execute 3 concurrent calls to getAlerts, 3 to getAirQuality, 3 to reverseGeocode, 3 to updatePreferences simultaneously
        res = driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            Promise.all([
                window.apiClient.getAlerts('Coimbatore', 11.0168, 76.9558),
                window.apiClient.getAlerts('Coimbatore', 11.0168, 76.9558),
                window.apiClient.getAlerts('Coimbatore', 11.0168, 76.9558),
                window.apiClient.getAirQuality('Coimbatore', 11.0168, 76.9558),
                window.apiClient.getAirQuality('Coimbatore', 11.0168, 76.9558),
                window.apiClient.getAirQuality('Coimbatore', 11.0168, 76.9558),
                window.apiClient.reverseGeocode(11.0168, 76.9558),
                window.apiClient.reverseGeocode(11.0168, 76.9558),
                window.apiClient.reverseGeocode(11.0168, 76.9558),
                window.apiClient.updatePreferences({ last_known_location: 'Coimbatore', last_latitude: 11.0168, last_longitude: 76.9558 }),
                window.apiClient.updatePreferences({ last_known_location: 'Coimbatore', last_latitude: 11.0168, last_longitude: 76.9558 }),
                window.apiClient.updatePreferences({ last_known_location: 'Coimbatore', last_latitude: 11.0168, last_longitude: 76.9558 })
            ]).then(() => done({ success: true })).catch(err => done({ error: err.message }));
        """)

        time.sleep(1)
        logs = driver.get_log("performance")
        requests = []
        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                if msg["method"] == "Network.requestWillBeSent":
                    url = msg["params"]["request"]["url"]
                    method = msg["params"]["request"]["method"]
                    if method != "OPTIONS":
                        requests.append((method, url))
            except Exception:
                pass

        counts = {}
        for m, u in requests:
            for target in ["alerts", "air-quality", "preferences", "reverse"]:
                if target in u:
                    counts[target] = counts.get(target, 0) + 1

        return requests, counts
    finally:
        driver.quit()

if __name__ == "__main__":
    print("=== TEST 1: HOME PAGE LOAD (GPS GRANTED) ===")
    reqs_granted, counts_granted = run_test_granted()
    for m, u in reqs_granted:
        for t in ["alerts", "air-quality", "preferences", "reverse"]:
            if t in u:
                print(f"  [{t.upper()}] {m} {u}")
    print("Counts (GPS Granted):", counts_granted)

    print("\n=== TEST 2: HOME PAGE LOAD (PERMISSION DENIED/DISMISSED) ===")
    reqs_denied, counts_denied = run_test_denied()
    for m, u in reqs_denied:
        for t in ["alerts", "air-quality", "preferences", "reverse"]:
            if t in u:
                print(f"  [{t.upper()}] {m} {u}")
    print("Counts (Permission Denied):", counts_denied)

    print("\n=== TEST 3: CONCURRENT IN-FLIGHT DEDUPLICATION (3x concurrent calls each) ===")
    reqs_concurrent, counts_concurrent = run_in_flight_dedup_test()
    for m, u in reqs_concurrent:
        for t in ["alerts", "air-quality", "preferences", "reverse"]:
            if t in u:
                print(f"  [{t.upper()}] {m} {u}")
    print("Counts (Concurrent 3x calls each):", counts_concurrent)
