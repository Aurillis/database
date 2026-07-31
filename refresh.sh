#!/bin/bash
# 刷新报告门户 - 复制新的 HTML 报告并重新生成元数据
# 用法: bash refresh.sh [源目录]
# 默认源目录: ~/Downloads

SOURCE="${1:-/c/Users/cbbyy/Downloads}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORTS_DIR="$SCRIPT_DIR/reports"
PYTHON="C:\Users\cbbyy\.workbuddy\binaries\python\versions\3.13.12\python.exe"

echo "=== 刷新报告门户 ==="
echo "源目录: $SOURCE"
echo "报告目录: $REPORTS_DIR"
echo ""

# 复制 HTML 文件
echo "[1/2] 复制 HTML 报告文件..."
count=0
find "$SOURCE" -maxdepth 1 -name "*.html" -type f -print0 | while IFS= read -r -d '' file; do
  cp "$file" "$REPORTS_DIR/"
  count=$((count + 1))
done
total=$(find "$SOURCE" -maxdepth 1 -name "*.html" -type f | wc -l)
echo "  已复制 $total 个文件"

# 重新提取元数据
echo "[2/2] 提取报告元数据..."
"$PYTHON" "$SCRIPT_DIR/extract_meta.py"

echo ""
echo "=== 完成! ==="
echo "报告总数: $total"
echo "门户地址: http://localhost:8765"
echo ""
echo "如需启动服务器, 运行:"
echo "  cd \"$SCRIPT_DIR\" && \"$PYTHON\" -m http.server 8765"
