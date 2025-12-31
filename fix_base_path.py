"""
批量修改前端HTML文件以支持 base path
支持根路径 (/) 和子路径 (/agent/) 部署
"""

import re
import sys
from pathlib import Path

# 设置UTF-8编码输出（解决Windows下emoji显示问题）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 全局配置代码（插入到每个页面的 <script> 开头）
BASE_PATH_CONFIG = """        // === 全局配置：自动检测部署路径 ===
        const BASE_PATH = (() => {
            const path = window.location.pathname;
            if (path.startsWith('/agent/')) return '/agent';
            return '';
        })();
        const API_BASE_URL = window.location.origin + BASE_PATH;
        const getFullPath = (p) => BASE_PATH + (p.startsWith('/') ? p : '/' + p);
        const navigateTo = (p) => window.location.href = getFullPath(p);
        // =========================================
"""

def process_html_file(file_path):
    """处理单个HTML文件"""
    print(f"处理文件: {file_path.name}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 1. 如果已经有配置代码，跳过
    if 'const BASE_PATH = (' in content:
        print(f"  ✓ {file_path.name} 已包含配置，跳过")
        return

    # 2. 替换 API_BASE_URL
    content = re.sub(
        r'const API_BASE_URL = window\.location\.origin;',
        BASE_PATH_CONFIG,
        content,
        count=1
    )

    # 3. 替换 window.location.href = '...' 为 navigateTo('...')
    # 匹配类似: window.location.href = '/xxx' 或 window.location.href = isAdmin ? '/admin' : '/'
    content = re.sub(
        r"window\.location\.href = (['\"]/.+?['\"])",
        r"navigateTo(\1)",
        content
    )

    # 处理三元表达式
    content = re.sub(
        r"window\.location\.href = (.+? \? ['\"]/.+?['\"] : ['\"]/.+?['\"])",
        r"navigateTo(\1)",
        content
    )

    # 4. 替换 HTML 链接中的 href="/xxx" 为动态链接
    # 匹配 <a href="/xxx">  但跳过 href="#"
    def replace_link(match):
        full_match = match.group(0)
        href_value = match.group(1)

        # 跳过已经有 onclick 的链接
        if 'onclick' in full_match:
            return full_match

        # 跳过 # 链接
        if href_value.startswith('#'):
            return full_match

        # 跳过外部链接
        if href_value.startswith('http'):
            return full_match

        # 替换为动态链接
        return f'<a href="#" onclick="event.preventDefault(); navigateTo(\'{href_value}\');"'

    content = re.sub(
        r'<a href="(/[^"]+?)"',
        replace_link,
        content
    )

    # 5. WebSocket URL 修改（如果有）
    # ws://127.0.0.1:8001/ws/ -> ${WS_BASE_URL}/ws/
    if 'new WebSocket(' in content and 'ws://' in content:
        # 添加 WS_BASE_URL 定义（在 BASE_PATH_CONFIG 之后）
        if 'WS_BASE_URL' not in content:
            ws_config = """
        const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const WS_BASE_URL = `${WS_PROTOCOL}//${window.location.host}${BASE_PATH}`;
"""
            content = content.replace(
                '        // =========================================',
                ws_config + '        // ========================================='
            )

    # 6. 只有内容变化了才保存
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ {file_path.name} 已更新")
    else:
        print(f"  - {file_path.name} 无需更新")

def main():
    """主函数"""
    static_dir = Path('static')

    print("🔧 开始批量修改HTML文件以支持 base path...")
    print("")

    # 获取所有HTML文件
    html_files = list(static_dir.glob('*.html'))

    print(f"找到 {len(html_files)} 个HTML文件")
    print("")

    for html_file in html_files:
        process_html_file(html_file)

    print("")
    print("✅ 所有文件处理完成！")
    print("")
    print("现在前端支持两种部署方式：")
    print("  1. 根路径部署: https://domain.com/")
    print("  2. 子路径部署: https://domain.com/agent/")
    print("")
    print("系统会自动检测并适配路径！")

if __name__ == '__main__':
    main()
