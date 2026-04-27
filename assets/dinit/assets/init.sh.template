#!/bin/bash
set -e

echo "正在初始化 [PROJECT_NAME]..."

# 安装依赖
if [ ! -d "node_modules" ]; then
    [INSTALL_COMMAND]
fi

# 启动开发服务器
echo "正在启动开发服务器..."
[DEV_COMMAND] &

echo "环境已就绪。"
