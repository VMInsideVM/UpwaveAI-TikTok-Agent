import requests
import sys

BASE_URL = "http://127.0.0.1:8001"


def login(username, password):
    url = f"{BASE_URL}/api/auth/login"
    data = {"username": username, "password": password}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    print(f"Login failed for {username}: {response.text}")
    return None


def verify_appeal_flow():
    print("Testing Appeal System Flow...")

    import os
    from dotenv import load_dotenv

    load_dotenv()
    admin_token = login("admin", os.getenv("INITIAL_ADMIN_PASSWORD", ""))
    if not admin_token:
        print("Skipping verification: Admin login failed.")
        return

    print("\n[1] Submitting Appeal...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    appeal_data = {
        "title": "Test Appeal from Script",
        "details": "This is a detailed description of the problem.",
        "session_id": None,
    }

    response = requests.post(
        f"{BASE_URL}/api/appeals", json=appeal_data, headers=headers
    )
    if response.status_code == 200:
        print("✅ Appeal submitted successfully.")
        appeal_id = response.json()["appeal_id"]
    elif response.status_code == 429:
        print("⚠️ Rate limit reached (Expected if run multiple times).")
        response = requests.get(f"{BASE_URL}/api/appeals", headers=headers)
        if response.status_code == 200 and len(response.json()) > 0:
            appeal_id = response.json()[0]["appeal_id"]
            print(f"Using existing appeal ID: {appeal_id}")
        else:
            print("Failed to get appeal ID. Exiting.")
            return
    else:
        print(f"❌ Submission failed: {response.text}")
        return

    print("\n[2] Testing Rate Limit (Submitting duplicate)...")
    response = requests.post(
        f"{BASE_URL}/api/appeals", json=appeal_data, headers=headers
    )
    if response.status_code == 429:
        print("✅ Rate limit working correctly (429 returned).")
    else:
        print(f"❌ Rate limit failed! Status: {response.status_code}")

    print("\n[3] Admin Listing Appeals...")
    response = requests.get(f"{BASE_URL}/api/admin/appeals", headers=headers)
    if response.status_code == 200:
        appeals = response.json()
        print(f"✅ Admin can see {len(appeals)} appeals.")
    else:
        print(f"❌ Admin list failed: {response.text}")

    print("\n[4] Resolving Appeal...")
    resolve_data = {
        "status": "resolved",
        "comment": "Resolved via verification script.",
    }
    response = requests.put(
        f"{BASE_URL}/api/admin/appeals/{appeal_id}", json=resolve_data, headers=headers
    )
    if response.status_code == 200:
        print("✅ Appeal resolved successfully.")
    else:
        print(f"❌ Resolution failed: {response.text}")

    print("\nVerification Complete.")


if __name__ == "__main__":
    verify_appeal_flow()
