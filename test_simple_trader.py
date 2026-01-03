#!/usr/bin/env python3
"""
简化版交易机器人 - 跳过 RAG 过滤，直接使用前 N 个事件
"""

import sys
import os
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from agents.polymarket.polymarket import Polymarket
from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.application.executor import Executor

class SimpleTrader:
    def __init__(self):
        self.polymarket = Polymarket()
        self.gamma = Gamma()
        self.agent = Executor()

    def run_simple_trade(self):
        """简化版交易流程 - 跳过 RAG 过滤"""
        print("=" * 60)
        print("简化版交易机器人")
        print("=" * 60)
        
        try:
            # Step 1: 获取可交易事件
            print("\nStep 1: Getting tradeable events...")
            events = self.polymarket.get_all_tradeable_events(limit=50, max_events=100, min_tradeable=5)
            print(f"✓ Found {len(events)} tradeable events")
            
            if len(events) == 0:
                print("No tradeable events found. Exiting.")
                return
            
            # Step 2: 直接选择前 3 个事件（跳过 RAG 过滤）
            print("\nStep 2: Selecting top 3 events (skipping RAG filter)...")
            selected_events = events[:3]
            print(f"✓ Selected {len(selected_events)} events")
            
            for i, event in enumerate(selected_events):
                print(f"  {i+1}. {event.title}")
                print(f"     Markets: {event.markets[:50]}..." if len(event.markets) > 50 else f"     Markets: {event.markets}")
            
            # Step 3: 直接获取可交易的市场（跳过事件映射）
            print("\nStep 3: Getting directly tradeable markets from Gamma API...")
            try:
                # 获取可交易的市场
                tradeable_markets = self.gamma.get_clob_tradable_markets(limit=10)
                print(f"✓ Found {len(tradeable_markets)} tradeable markets from Gamma API")
                
                # 转换为 SimpleMarket 格式
                markets = []
                for market in tradeable_markets:
                    try:
                        formatted_market_data = self.polymarket.map_api_to_market(market)
                        markets.append(formatted_market_data)
                    except Exception as e:
                        print(f"Error formatting market {market.get('id', 'unknown')}: {e}")
                        continue
                
                print(f"✓ Successfully formatted {len(markets)} markets")
                
            except Exception as e:
                print(f"Error getting tradeable markets: {e}")
                import traceback
                traceback.print_exc()
                markets = []
            
            if len(markets) == 0:
                print("No markets found. Exiting.")
                return
            
            # Step 4: 选择前 2 个市场（跳过 RAG 过滤）
            print("\nStep 4: Selecting top 2 markets (skipping RAG filter)...")
            selected_markets = markets[:2]
            print(f"✓ Selected {len(selected_markets)} markets")
            
            for i, market in enumerate(selected_markets):
                print(f"  {i+1}. {market['question']}")
                print(f"     Prices: {market['outcome_prices']}")
            
            # Step 5: 计算最佳交易
            print("\nStep 5: Calculating best trade for first market...")
            market = selected_markets[0]
            
            # 手动构建市场对象（模拟 RAG 返回格式）
            from langchain_core.documents import Document
            market_doc = Document(
                page_content=market['description'],
                metadata={
                    "id": market['id'],
                    "question": market['question'],
                    "outcomes": market['outcomes'],
                    "outcome_prices": market['outcome_prices'],
                    "clob_token_ids": market['clob_token_ids']
                }
            )
            market_tuple = (market_doc, 0.9)  # (Document, score)
            
            best_trade = self.agent.source_best_trade(market_tuple)
            print(f"✓ Calculated trade: {best_trade}")
            
            # Step 6: 格式化交易金额
            print("\nStep 6: Formatting trade amount...")
            amount = self.agent.format_trade_prompt_for_execution(best_trade)
            print(f"✓ Trade amount: ${amount:.2f}")
            
            # 显示交易摘要
            print("\n" + "=" * 60)
            print("交易摘要")
            print("=" * 60)
            print(f"市场: {market.question}")
            print(f"交易: {best_trade}")
            print(f"金额: ${amount:.2f}")
            print(f"USDC 余额: ${self.polymarket.get_usdc_balance():.2f}")
            print("=" * 60)
            
            print("\n✅ 简化版交易流程完成！")
            print("\n注意: 实际交易已被禁用。如需启用，请取消注释 execute_market_order 调用。")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    trader = SimpleTrader()
    trader.run_simple_trade()
