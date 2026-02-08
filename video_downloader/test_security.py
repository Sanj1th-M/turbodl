import requests
import time

BASE_URL = "http://127.0.0.1:8008"

def test_public_access():
    print("Testing Public Access (Should be blocked)...")
    try:
        # Try to analyze without auth
        res = requests.post(f"{BASE_URL}/analyze", json={"url": "http://example.com"})
        if res.status_code == 401:
            print("PASS: /analyze blocked (401)")
        else:
            print(f"FAIL: /analyze returned {res.status_code}")
            
        # Try to download without auth
        res = requests.post(f"{BASE_URL}/download", json={"url": "http://example.com", "format_id": "best", "is_audio": False})
        if res.status_code == 401:
            print("PASS: /download blocked (401)")
        else:
             print(f"FAIL: /download returned {res.status_code}")

    except Exception as e:
        print(f"ERROR: {e}")

def test_login_flow():
    print("\nTesting Login Flow...")
    session = requests.Session()
    
    # Login with wrong credentials
    res = requests.post(f"{BASE_URL}/login", data={"username": "admin", "password": "wrongpassword"})
    if res.status_code == 401:
        print("PASS: Wrong password rejected")
    else:
        print(f"FAIL: Wrong password returned {res.status_code}")

    # Login with correct credentials (default: admin/secret)
    res = requests.post(f"{BASE_URL}/login", data={"username": "admin", "password": "secret"})
    if res.status_code == 200:
        print("PASS: Login successful")
        token = res.json().get("access_token")
        if token:
            print("PASS: Token received")
            # Set cookie manually if not automatically handled by session (it should be)
            # But the response body has token, also set-cookie header.
            # verify cookie
            if 'access_token' in res.cookies:
                 print("PASS: Cookie set")
            else:
                 print("FAIL: Cookie missing")
        else:
            print("FAIL: Token missing in response")
    else:
        print(f"FAIL: Login failed {res.status_code} - {res.text}")
        return

    # Authorized Access
    print("\nTesting Authorized Access...")
    # Use the session which has the cookie
    # Testing analyze (validation might fail but auth should pass)
    res = session.post(f"{BASE_URL}/analyze", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    if res.status_code != 401:
        print(f"PASS: /analyze authorized (Status: {res.status_code})")
    else:
        print("FAIL: /analyze still 401 after login")

if __name__ == "__main__":
    test_public_access()
    test_login_flow()
