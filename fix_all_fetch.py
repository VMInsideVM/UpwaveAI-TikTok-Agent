#!/usr/bin/env python3
"""
批量替换所有带 Authorization header 的 fetch 调用为 fetchWithAuth
"""
import re

def fix_fetch_calls(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    replacements = 0

    # 模式1: 多行格式
    # await fetch(`${API_BASE_URL}/xxx`, {
    #     headers: {
    #         'Authorization': `Bearer ${accessToken}`
    #     }
    # })
    pattern1 = r'await fetch\(\`\$\{API_BASE_URL\}([^`]+)\`,\s*\{\s*headers:\s*\{\s*[\'"]Authorization[\'"]:.*?\}\s*\}\)'

    def replace_fn1(match):
        nonlocal replacements
        url_path = match.group(1)
        # 跳过 refresh API（会导致循环）
        if '/auth/refresh' in url_path:
            return match.group(0)
        replacements += 1
        return f'await fetchWithAuth(`${{API_BASE_URL}}{url_path}`)'

    content = re.sub(pattern1, replace_fn1, content, flags=re.DOTALL)

    # 模式2: 单行格式
    # fetch(`${API_BASE_URL}/xxx`, { headers: { 'Authorization': ... } })
    pattern2 = r'await fetch\(\`\$\{API_BASE_URL\}([^`]+)\`,\s*\{\s*headers:\s*\{\s*[\'"]Authorization[\'"]:.*?\}\s*\}\)'

    def replace_fn2(match):
        nonlocal replacements
        url_path = match.group(1)
        if '/auth/refresh' in url_path:
            return match.group(0)
        replacements += 1
        return f'await fetchWithAuth(`${{API_BASE_URL}}{url_path}`)'

    content = re.sub(pattern2, replace_fn2, content)

    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Fixed {replacements} fetch calls!")
        print(f"[INFO] File updated: {file_path}")
    else:
        print("[INFO] No changes needed")

if __name__ == '__main__':
    fix_fetch_calls('static/index.html')
