#!/bin/bash
# 数字人系统安装脚本

echo "安装数字人系统依赖..."

# 安装Python依赖
pip3 install jieba

# 设置执行权限
chmod +x main.py

echo "安装完成！"
echo ""
echo "使用方法:"
echo "1. 启动数字人映射器:"
echo "   rosrun ymbot_kongzi_control digital_human_joint_mapper"
echo ""
echo "2. 运行数字人系统:"
echo "   python3 main.py                    # 交互模式"
echo "   python3 main.py '你好，欢迎！'      # 直接处理文本"
echo "   python3 main.py --test             # 运行测试序列"
echo "   python3 main.py --test-connection  # 测试连接"
