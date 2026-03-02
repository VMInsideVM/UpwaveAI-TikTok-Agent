"""
测试登录API
"""

import requests
import json

API_BASE_URL = "http://127.0.0.1:8001"


def test_login(username, password):
    """测试登录"""
    url = f"{API_BASE_URL}/api/auth/login"
    payload = {"username": username, "password": password}

    print(f"\n测试登录: {username}")
    print(f"请求URL: {url}")
    print(f"请求数据: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"}
        )

        print(f"\n状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print(f"响应内容: {response.text}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ 登录成功!")
            print(f"用户名: {data.get('username')}")
            print(f"Access Token: {data.get('access_token')[:50]}...")
            return True
        else:
            print(f"\n❌ 登录失败")
            try:
                error = response.json()
                print(f"错误信息: {error}")
            except:
                print(f"错误响应（非JSON）: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 请求异常: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "")

    # 测试admin
    test_login("admin", admin_password)

    # 测试错误密码
    test_login("admin", "wrongpassword")
