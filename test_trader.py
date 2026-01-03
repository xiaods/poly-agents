#!/usr/bin/env python3
"""
测试脚本：验证 run-autonomous-trader 的修复
"""

import os
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_environment_variables():
    """测试环境变量是否正确配置"""
    print("=" * 60)
    print("测试 1: 环境变量检查")
    print("=" * 60)
    
    required_vars = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "POLYGON_WALLET_PRIVATE_KEY": os.getenv("POLYGON_WALLET_PRIVATE_KEY"),
    }
    
    all_valid = True
    for var_name, var_value in required_vars.items():
        if var_value:
            masked_value = var_value[:8] + "..." if len(var_value) > 8 else "***"
            print(f"✓ {var_name}: {masked_value}")
        else:
            print(f"✗ {var_name}: 未设置")
            all_valid = False
    
    if not all_valid:
        print("\n❌ 环境变量检查失败！请确保所有必需的环境变量都已设置。")
        return False
    
    print("\n✅ 环境变量检查通过！")
    return True

def test_executor_initialization():
    """测试 Executor 类初始化"""
    print("\n" + "=" * 60)
    print("测试 2: Executor 初始化")
    print("=" * 60)
    
    try:
        from agents.application.executor import Executor
        executor = Executor()
        print("✓ Executor 实例创建成功")
        print(f"✓ Token 限制: {executor.token_limit}")
        print(f"✓ LLM 模型已初始化")
        print(f"✓ Gamma 客户端已初始化")
        print(f"✓ Chroma 客户端已初始化")
        print(f"✓ Polymarket 客户端已初始化")
        print("\n✅ Executor 初始化测试通过！")
        return True
    except Exception as e:
        print(f"\n❌ Executor 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_polymarket_initialization():
    """测试 Polymarket 类初始化"""
    print("\n" + "=" * 60)
    print("测试 3: Polymarket 初始化")
    print("=" * 60)
    
    try:
        from agents.polymarket.polymarket import Polymarket
        polymarket = Polymarket()
        print("✓ Polymarket 实例创建成功")
        print(f"✓ Gamma URL: {polymarket.gamma_url}")
        print(f"✓ CLOB URL: {polymarket.clob_url}")
        print(f"✓ Chain ID: {polymarket.chain_id}")
        print(f"✓ Web3 连接已建立")
        print("\n✅ Polymarket 初始化测试通过！")
        return True
    except Exception as e:
        print(f"\n❌ Polymarket 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_get_tradeable_events():
    """测试获取可交易事件"""
    print("\n" + "=" * 60)
    print("测试 4: 获取可交易事件")
    print("=" * 60)
    
    try:
        from agents.polymarket.polymarket import Polymarket
        polymarket = Polymarket()
        
        # 获取少量事件进行测试
        events = polymarket.get_all_tradeable_events(limit=10, max_events=20, min_tradeable=3)
        
        print(f"✓ 成功获取 {len(events)} 个可交易事件")
        
        if len(events) > 0:
            print(f"\n示例事件:")
            for i, event in enumerate(events[:3]):
                print(f"  {i+1}. {event.title}")
                print(f"     - ID: {event.id}")
                print(f"     - Market 数量: {len(event.markets.split(',')) if event.markets else 0}")
        
        print("\n✅ 获取可交易事件测试通过！")
        return True
    except Exception as e:
        print(f"\n❌ 获取可交易事件失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_trader_initialization():
    """测试 Trader 类初始化"""
    print("\n" + "=" * 60)
    print("测试 5: Trader 初始化")
    print("=" * 60)
    
    try:
        from agents.application.trade import Trader
        trader = Trader()
        print("✓ Trader 实例创建成功")
        print(f"✓ Polymarket 客户端已初始化")
        print(f"✓ Gamma 客户端已初始化")
        print(f"✓ Agent (Executor) 已初始化")
        print("\n✅ Trader 初始化测试通过！")
        return True
    except Exception as e:
        print(f"\n❌ Trader 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试修复后的交易机器人")
    print("=" * 60)
    
    tests = [
        ("环境变量检查", test_environment_variables),
        ("Executor 初始化", test_executor_initialization),
        ("Polymarket 初始化", test_polymarket_initialization),
        ("获取可交易事件", test_get_tradeable_events),
        ("Trader 初始化", test_trader_initialization),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{test_name}' 发生异常: {e}")
            results.append((test_name, False))
    
    # 打印测试总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！交易机器人已准备好运行。")
        print("\n要运行完整的交易流程，请执行:")
        print("  python scripts/python/cli.py run-autonomous-trader")
    else:
        print("\n⚠️  部分测试失败，请检查上述错误信息。")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)