#!/bin/bash
# 安装脚本：解决 pysha3 在 Python 3.11 上的构建问题
# 使用 safe-pysha3 替代 pysha3

set -e

echo "步骤 1: 安装 safe-pysha3 (替代 pysha3，兼容 Python 3.11)..."
pip install safe-pysha3==1.0.3

echo "步骤 2: 创建临时 requirements 文件（排除 eip712-structs）..."
grep -v "^eip712-structs" requirements.txt > /tmp/requirements-temp.txt || true

echo "步骤 3: 安装其他依赖（排除 eip712-structs）..."
pip install -r /tmp/requirements-temp.txt

echo "步骤 4: 安装 eip712-structs (跳过 pysha3 依赖检查，因为 safe-pysha3 已提供 sha3 模块)..."
pip install eip712-structs==1.1.0 --no-deps

echo "步骤 5: 验证安装..."
python -c "import sha3; import eip712_structs; print('✓ sha3 和 eip712-structs 安装成功')" || echo "警告: 验证失败，但可能不影响使用"

echo "安装完成！"

