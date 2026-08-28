#!/usr/bin/env bash
# 调研台「无死数据」红线检查脚本
# 用法：bash check_no_dead_data.sh  （在 research-deck/ 目录运行）
# 通过：输出 "PASS ✓ 无固定产品死数据"；失败：列出违规行并退出码 1
#
# 红线（用户 2026-08-29 要求，永久生效）：
#   任何维度/模板禁止写死固定产品的真实数据（品牌/销量/份额/类型清单等）。
#   只允许：LLM 实时生成（source=llm）或 通用结构骨架（source=template，数据标待生成）。

cd "$(dirname "$0")"

# 固定产品名/技术名黑名单（新增违规产品名请追加到这里）
BLACKLIST='盆底肌|哺乳按摩|Kegel|Momcozy|lactation|Intimate Rose|Perifit|LaVie|Frida|K-fit|iSTIM|QoQiu|EMG|EMS/TENS|Peltier|510k|NMPA'

echo "=== 无死数据红线检查 ==="
echo "检查文件: server.py index.html"
echo "黑名单: $BLACKLIST"
echo ""

FOUND=$(grep -nE "$BLACKLIST" server.py index.html 2>/dev/null)

if [ -n "$FOUND" ]; then
  echo "❌ 检测到固定产品死数据引用："
  echo "$FOUND"
  echo ""
  echo "违规！请删除相关死数据（改为通用骨架或 LLM 实时生成）后再提交。"
  exit 1
else
  echo "PASS ✓ 无固定产品死数据"
  exit 0
fi
