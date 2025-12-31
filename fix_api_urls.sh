#!/bin/bash

# ============================================
# 修复前端 API URL 硬编码问题
# ============================================

set -e

PROJECT_DIR="/root/UpwaveAI-TikTok-Agent"
STATIC_DIR="$PROJECT_DIR/static"

echo "🔧 修复前端 API URL..."
echo ""

# 备份 static 目录
echo "💾 备份 static 目录..."
cp -r "$STATIC_DIR" "$STATIC_DIR.backup.$(date +%Y%m%d_%H%M%S)"
echo "✅ 备份完成"
echo ""

# 查找所有 HTML 文件中的硬编码 URL
echo "🔍 搜索硬编码的 API URL..."
grep -rn "http://127.0.0.1:8001" "$STATIC_DIR" || echo "未找到 127.0.0.1:8001"
grep -rn "http://localhost:8001" "$STATIC_DIR" || echo "未找到 localhost:8001"
echo ""

# 替换所有硬编码的 API URL
echo "📝 替换 API URL..."

# 替换 http://127.0.0.1:8001/api/ -> /api/
find "$STATIC_DIR" -type f \( -name "*.html" -o -name "*.js" \) -exec sed -i \
    "s|http://127\.0\.0\.1:8001/api/|/api/|g" {} +

# 替换 http://localhost:8001/api/ -> /api/
find "$STATIC_DIR" -type f \( -name "*.html" -o -name "*.js" \) -exec sed -i \
    "s|http://localhost:8001/api/|/api/|g" {} +

# 替换 http://127.0.0.1:8001/ws/ -> /ws/
find "$STATIC_DIR" -type f \( -name "*.html" -o -name "*.js" \) -exec sed -i \
    "s|ws://127\.0\.0\.1:8001/ws/|/ws/|g" {} +

# 替换 http://localhost:8001/ws/ -> /ws/
find "$STATIC_DIR" -type f \( -name "*.html" -o -name "*.js" \) -exec sed -i \
    "s|ws://localhost:8001/ws/|/ws/|g" {} +

echo "✅ URL 替换完成"
echo ""

# 验证修改
echo "✅ 验证修改结果..."
echo ""
echo "剩余的硬编码 URL（应该为空）："
grep -rn "127\.0\.0\.1:8001\|localhost:8001" "$STATIC_DIR" || echo "✅ 所有硬编码 URL 已清除"
echo ""

echo "======================================"
echo "🎉 修复完成！"
echo "======================================"
echo ""
echo "💡 备份位置: $STATIC_DIR.backup.*"
echo ""
echo "🌐 现在可以通过以下方式访问："
echo "   - https://111.228.61.201"
echo "   - https://agent.upwaveai.com (需要 hosts 文件或 DNS 生效)"
echo ""
