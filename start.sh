#!/usr/bin/env bash
# 高考志愿填报规划 Agent —— 一键启动脚本
# 用法： ./start.sh      （首次运行会自动建虚拟环境并装依赖）
set -euo pipefail

cd "$(dirname "$0")"

# 1) 载入 .env（DEEPSEEK_API_KEY 等）
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# 2) 检查 API Key
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "❌ 未找到 DEEPSEEK_API_KEY。"
  echo "   请在本目录创建 .env 文件，写入一行："
  echo "       DEEPSEEK_API_KEY=sk-你的key"
  exit 1
fi

# 3) 确保虚拟环境
if [ ! -d .venv ]; then
  echo "📦 首次运行：创建虚拟环境 .venv ..."
  python3 -m venv .venv
fi

# 4) 确保依赖
if ! .venv/bin/python -c "import openai" 2>/dev/null; then
  echo "📦 安装依赖 openai ..."
  .venv/bin/pip install -q openai
fi

# 5) 后台开浏览器
PORT="${PORT:-8010}"
URL="http://127.0.0.1:${PORT}"
(
  sleep 1.5
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  fi
) >/dev/null 2>&1 &

# 6) 启动服务
echo "🚀 启动高考志愿填报 Agent：$URL"
echo "   按 Ctrl-C 停止服务。"
exec .venv/bin/python web_app.py
