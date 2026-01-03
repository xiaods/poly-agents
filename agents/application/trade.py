import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.application.executor import Executor as Agent
from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.polymarket.polymarket import Polymarket

import shutil


class Trader:
    def __init__(self):
        self.polymarket = Polymarket()
        self.gamma = Gamma()
        self.agent = Agent()

    def pre_trade_logic(self) -> None:
        self.clear_local_dbs()

    def clear_local_dbs(self) -> None:
        # Use absolute paths based on project root
        project_root = Path(__file__).parent.parent.parent
        events_db = project_root / "local_db_events"
        markets_db = project_root / "local_db_markets"
        
        try:
            if events_db.exists():
                shutil.rmtree(events_db)
                print(f"Cleared: {events_db}")
        except Exception as e:
            print(f"Error clearing events db: {e}")
        
        try:
            if markets_db.exists():
                shutil.rmtree(markets_db)
                print(f"Cleared: {markets_db}")
        except Exception as e:
            print(f"Error clearing markets db: {e}")

    def one_best_trade(self, max_retries: int = 3, retry_count: int = 0) -> None:
        """

        one_best_trade is a strategy that evaluates all events, markets, and orderbooks

        leverages all available information sources accessible to the autonomous agent

        then executes that trade without any human intervention

        """
        try:
            self.pre_trade_logic()

            print("Step 1: Getting tradeable events...")
            events = self.polymarket.get_all_tradeable_events(limit=100, max_events=500, min_tradeable=10)
            print(f"1. FOUND {len(events)} EVENTS")
            
            if len(events) == 0:
                print("No tradeable events found. Exiting.")
                return

            print("Step 2: Filtering events with RAG (this may take a while)...")
            filtered_events = self.agent.filter_events_with_rag(events)
            print(f"2. FILTERED {len(filtered_events)} EVENTS")
            
            if len(filtered_events) == 0:
                print("No events passed RAG filtering. Exiting.")
                return

            print("Step 3: Mapping events to markets...")
            markets = self.agent.map_filtered_events_to_markets(filtered_events)
            print(f"3. FOUND {len(markets)} MARKETS")
            
            if len(markets) == 0:
                print("No markets found. Exiting.")
                return

            print("Step 4: Filtering markets with RAG...")
            filtered_markets = self.agent.filter_markets(markets)
            print(f"4. FILTERED {len(filtered_markets)} MARKETS")
            
            if len(filtered_markets) == 0:
                print("No markets passed RAG filtering. Exiting.")
                return

            print("Step 5: Calculating best trade...")
            market = filtered_markets[0]
            best_trade = self.agent.source_best_trade(market)
            print(f"5. CALCULATED TRADE {best_trade}")

            print("Step 6: Formatting trade amount...")
            amount = self.agent.format_trade_prompt_for_execution(best_trade)
            print(f"6. TRADE AMOUNT: {amount}")
            
            print("\n=== Trade Summary ===")
            print(f"Market: {market[0].dict()['metadata']['question']}")
            print(f"Trade: {best_trade}")
            print(f"Amount: ${amount:.2f}")
            print(f"USDC Balance: ${self.polymarket.get_usdc_balance():.2f}")
            print("=" * 50)
            
            # Please refer to TOS before uncommenting: polymarket.com/tos
            # trade = self.polymarket.execute_market_order(market, amount)
            # print(f"7. TRADED {trade}")

        except Exception as e:
            import traceback
            print(f"Error: {e}")
            print("\nFull traceback:")
            traceback.print_exc()
            
            if retry_count < max_retries:
                print(f"\nRetrying... (Attempt {retry_count + 1}/{max_retries})")
                self.one_best_trade(max_retries=max_retries, retry_count=retry_count + 1)
            else:
                print(f"\nMax retries ({max_retries}) reached. Giving up.")
                raise

    def maintain_positions(self):
        pass

    def incentive_farm(self):
        pass


if __name__ == "__main__":
    t = Trader()
    t.one_best_trade()
