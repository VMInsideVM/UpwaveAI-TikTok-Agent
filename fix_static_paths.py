"""
修复静态资源路径以支持 base path
将 /static/ 替换为动态路径
"""

import re
import sys
from pathlib import Path

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def fix_static_paths_in_file(file_path):
    """修复单个文件中的静态资源路径"""
    print(f"处理文件: {file_path.name}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 1. 修复 <img src="/static/...">
    # 替换为 JavaScript 模板字符串（需要在 script 中执行）
    # 但这对于 HTML 标签不适用，所以我们需要另一个策略

    # 策略：在 </head> 之前添加一个 script 来动态设置 favicon
    # 然后移除硬编码的 favicon link

    # 移除硬编码的 favicon
    content = re.sub(
        r'<link rel="icon" href="/static/logo\.png" type="image/png">',
        '<!-- Favicon will be set dynamically -->',
        content
    )

    # 在第一个 <script> 标签中添加动态设置 favicon 的代码
    # 找到 BASE_PATH 配置后面
    if 'const BASE_PATH = (' in content:
        # 在 BASE_PATH 配置后添加 favicon 设置
        favicon_code = """
        // 动态设置 favicon
        const setFavicon = () => {
            const link = document.querySelector("link[rel*='icon']") || document.createElement('link');
            link.type = 'image/png';
            link.rel = 'icon';
            link.href = `${BASE_PATH}/static/logo.png`;
            document.getElementsByTagName('head')[0].appendChild(link);
        };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setFavicon);
        } else {
            setFavicon();
        }
"""

        content = content.replace(
            '        // =========================================',
            favicon_code + '        // ========================================='
        )

    # 2. 对于 <img> 标签，添加一个函数在页面加载后修复
    if '<img src="/static/' in content:
        # 在脚本中添加修复图片路径的函数
        fix_images_code = """
        // 修复图片路径
        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('img[src^="/static/"]').forEach(img => {
                const originalSrc = img.getAttribute('src');
                img.src = `${BASE_PATH}${originalSrc}`;
            });
        });
"""

        if 'document.addEventListener(\'DOMContentLoaded\'' not in content or content.count('DOMContentLoaded') < 2:
            content = content.replace(
                '        // =========================================',
                fix_images_code + '        // ========================================='
            )

    # 保存修改
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ {file_path.name} 已更新")
    else:
        print(f"  - {file_path.name} 无需更新")

def main():
    """主函数"""
    static_dir = Path('static')

    print("🔧 修复静态资源路径...")
    print("")

    html_files = list(static_dir.glob('*.html'))

    # 排除测试文件
    html_files = [f for f in html_files if f.name != 'test-path.html']

    print(f"找到 {len(html_files)} 个HTML文件")
    print("")

    for html_file in html_files:
        fix_static_paths_in_file(html_file)

    print("")
    print("✅ 静态资源路径修复完成！")
    print("")
    print("💡 建议：同时在 Nginx 配置中添加 /agent/static/ 反向代理")

if __name__ == '__main__':
    main()
