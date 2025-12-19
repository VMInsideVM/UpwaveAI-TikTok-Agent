"""
测试管理员API新增功能

测试以下功能:
1. 修改用户信息（用户名、邮箱、手机号、密码）
2. 查看报告详情
"""

import requests
import json

# 配置
API_BASE_URL = "http://127.0.0.1:8001"

def test_admin_login():
    """测试管理员登录"""
    print("=" * 60)
    print("测试 1: 管理员登录")
    print("=" * 60)

    response = requests.post(
        f"{API_BASE_URL}/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "***REMOVED***"
        }
    )

    if response.status_code == 200:
        data = response.json()
        token = data["access_token"]
        print(f"✅ 登录成功")
        print(f"   Token: {token[:50]}...")
        print(f"   用户: {data['user']['username']}")
        print(f"   管理员: {data['user']['is_admin']}")
        return token
    else:
        print(f"❌ 登录失败: {response.text}")
        return None


def test_update_user_info(token, user_id):
    """测试修改用户信息"""
    print("\n" + "=" * 60)
    print("测试 2: 修改用户信息")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 先获取当前用户信息
    users_response = requests.get(
        f"{API_BASE_URL}/api/admin/users",
        headers=headers
    )

    if users_response.status_code != 200:
        print(f"❌ 获取用户列表失败: {users_response.text}")
        return False

    users = users_response.json()
    if not users:
        print("❌ 没有可测试的用户")
        return False

    # 使用第一个非管理员用户进行测试
    test_user = None
    for user in users:
        if not user['is_admin']:
            test_user = user
            break

    if not test_user:
        print("❌ 没有找到非管理员用户")
        return False

    user_id = test_user['user_id']
    print(f"\n测试用户: {test_user['username']} ({user_id})")
    print(f"当前信息:")
    print(f"  用户名: {test_user['username']}")
    print(f"  邮箱: {test_user['email']}")
    print(f"  手机号: {test_user.get('phone_number', '未设置')}")

    # 测试修改用户名
    print(f"\n【测试 2.1】修改用户名")
    update_data = {
        "username": f"test_modified_{test_user['username']}"
    }

    response = requests.put(
        f"{API_BASE_URL}/api/admin/users/{user_id}",
        headers=headers,
        json=update_data
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 修改成功")
        print(f"   旧用户名: {result['old_info']['username']}")
        print(f"   新用户名: {result['new_info']['username']}")
    else:
        print(f"❌ 修改失败: {response.text}")
        return False

    # 测试修改邮箱
    print(f"\n【测试 2.2】修改邮箱")
    update_data = {
        "email": f"modified_{test_user['email']}"
    }

    response = requests.put(
        f"{API_BASE_URL}/api/admin/users/{user_id}",
        headers=headers,
        json=update_data
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 修改成功")
        print(f"   旧邮箱: {result['old_info']['email']}")
        print(f"   新邮箱: {result['new_info']['email']}")
    else:
        print(f"❌ 修改失败: {response.text}")
        return False

    # 测试修改手机号
    print(f"\n【测试 2.3】修改手机号")
    update_data = {
        "phone_number": "13900000001"
    }

    response = requests.put(
        f"{API_BASE_URL}/api/admin/users/{user_id}",
        headers=headers,
        json=update_data
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 修改成功")
        print(f"   旧手机号: {result['old_info'].get('phone_number', '未设置')}")
        print(f"   新手机号: {result['new_info']['phone_number']}")
    else:
        print(f"❌ 修改失败: {response.text}")
        return False

    # 测试修改密码
    print(f"\n【测试 2.4】修改密码")
    update_data = {
        "password": "new_test_password_123"
    }

    response = requests.put(
        f"{API_BASE_URL}/api/admin/users/{user_id}",
        headers=headers,
        json=update_data
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 修改成功")
        print(f"   密码已更新: {result['new_info']['password_updated']}")
    else:
        print(f"❌ 修改失败: {response.text}")
        return False

    # 测试一次性修改多个字段
    print(f"\n【测试 2.5】一次性修改多个字段")
    update_data = {
        "username": f"final_{test_user['username']}",
        "email": f"final_{test_user['email']}",
        "phone_number": "13900000002"
    }

    response = requests.put(
        f"{API_BASE_URL}/api/admin/users/{user_id}",
        headers=headers,
        json=update_data
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 修改成功")
        print(f"   变更内容:")
        print(f"     用户名: {result['old_info']['username']} → {result['new_info']['username']}")
        print(f"     邮箱: {result['old_info']['email']} → {result['new_info']['email']}")
        print(f"     手机号: {result['old_info'].get('phone_number', '未设置')} → {result['new_info']['phone_number']}")
    else:
        print(f"❌ 修改失败: {response.text}")
        return False

    # 测试唯一性检查（尝试使用已存在的用户名）
    print(f"\n【测试 2.6】唯一性检查（应该失败）")
    if len(users) > 1:
        another_user = users[1 if users[0]['user_id'] == user_id else 0]
        update_data = {
            "username": another_user['username']
        }

        response = requests.put(
            f"{API_BASE_URL}/api/admin/users/{user_id}",
            headers=headers,
            json=update_data
        )

        if response.status_code == 400:
            print(f"✅ 唯一性检查生效")
            print(f"   错误信息: {response.json()['detail']}")
        else:
            print(f"❌ 唯一性检查失败（应该拒绝重复的用户名）")
            return False

    return True


def test_get_report_detail(token):
    """测试查看报告详情"""
    print("\n" + "=" * 60)
    print("测试 3: 查看报告详情")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 获取报告列表
    response = requests.get(
        f"{API_BASE_URL}/api/admin/reports",
        headers=headers
    )

    if response.status_code != 200:
        print(f"❌ 获取报告列表失败: {response.text}")
        return False

    reports = response.json()

    if not reports:
        print("⚠️ 没有报告可测试")
        print("   建议: 先生成一些报告，然后再运行此测试")
        return True  # 不算失败

    print(f"\n找到 {len(reports)} 个报告")

    # 测试查看第一个报告的详情
    test_report = reports[0]
    report_id = test_report['report_id']

    print(f"\n查看报告: {test_report['title']}")
    print(f"  报告ID: {report_id}")
    print(f"  用户: {test_report['username']}")
    print(f"  状态: {test_report['status']}")

    # 获取详情
    response = requests.get(
        f"{API_BASE_URL}/api/admin/reports/{report_id}",
        headers=headers
    )

    if response.status_code != 200:
        print(f"❌ 获取报告详情失败: {response.text}")
        return False

    detail = response.json()

    print(f"\n✅ 获取报告详情成功")
    print(f"   报告ID: {detail['report_id']}")
    print(f"   标题: {detail['title']}")
    print(f"   状态: {detail['status']}")
    print(f"   用户: {detail['username']} ({detail['user_email']})")
    print(f"   创建时间: {detail['created_at']}")
    print(f"   完成时间: {detail.get('completed_at', '未完成')}")
    print(f"   会话ID: {detail['session_id']}")
    print(f"   报告路径: {detail.get('report_path', '无')}")

    if detail.get('report_content'):
        content_preview = detail['report_content'][:100]
        print(f"   内容预览: {content_preview}...")
    else:
        print(f"   内容: 无")

    if detail.get('report_data'):
        print(f"   JSON数据: 包含 {len(detail['report_data'])} 条记录")
    else:
        print(f"   JSON数据: 无")

    if detail.get('error_message'):
        print(f"   错误信息: {detail['error_message']}")

    return True


def main():
    print("\n" + "=" * 60)
    print("管理员API新增功能测试")
    print("=" * 60 + "\n")

    # 1. 管理员登录
    token = test_admin_login()

    if not token:
        print("\n❌ 管理员登录失败，无法继续测试")
        print("   请确保:")
        print("   1. 服务已启动 (python start_chatbot.py)")
        print("   2. 管理员账号存在")
        print("   3. 密码正确")
        return

    # 2. 测试修改用户信息
    success_update = test_update_user_info(token, None)

    # 3. 测试查看报告详情
    success_report = test_get_report_detail(token)

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    results = [
        ("管理员登录", True),
        ("修改用户信息", success_update),
        ("查看报告详情", success_report)
    ]

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器")
        print("   请确保服务已启动: python start_chatbot.py")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
