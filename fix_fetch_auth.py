#!/usr/bin/env python3
"""
批量替换 static/index.html 中的 fetch 调用为 fetchWithAuth
"""
import re

def fix_fetch_calls(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 模式1: 匹配带 Authorization header 的 fetch 调用
    # await fetch(`${API_BASE_URL}/...`, {
    #     headers: {
    #         'Authorization': `Bearer ${accessToken}`
    #     }
    # })
    pattern1 = r'await fetch\(\`\$\{API_BASE_URL\}([^`]+)\`,\s*\{\s*headers:\s*\{\s*[\'"]Authorization[\'"]:.*?\$\{accessToken\}.*?\}\s*\}\)'

    def replace_fn1(match):
        url_path = match.group(1)
        # 跳过 refresh token 的 API 调用（会导致循环）
        if '/auth/refresh' in url_path:
            return match.group(0)
        return f'await fetchWithAuth(`${{API_BASE_URL}}{url_path}`)'

    content = re.sub(pattern1, replace_fn1, content, flags=re.DOTALL)

    # 统计修改数量
    changes = content != original_content
    if changes:
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Fixed! File updated: {file_path}")

        # 统计修改行数
        original_lines = original_content.split('\n')
        new_lines = content.split('\n')
        changed_lines = sum(1 for i in range(min(len(original_lines), len(new_lines)))
                           if original_lines[i] != new_lines[i])
        print(f"[INFO] Changed approximately {changed_lines} lines")
    else:
        print("[INFO] No changes needed")

    return changes

if __name__ == '__main__':
    file_path = 'static/index.html'
    fix_fetch_calls(file_path)
