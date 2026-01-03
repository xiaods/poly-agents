import os
import json
import ast
import re
from typing import List, Dict, Any

import math

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.connectors.chroma import PolymarketRAG as Chroma
from agents.utils.objects import SimpleEvent, SimpleMarket
from agents.application.prompts import Prompter
from agents.polymarket.polymarket import Polymarket

def retain_keys(data, keys_to_retain):
    if isinstance(data, dict):
        return {
            key: retain_keys(value, keys_to_retain)
            for key, value in data.items()
            if key in keys_to_retain
        }
    elif isinstance(data, list):
        return [retain_keys(item, keys_to_retain) for item in data]
    else:
        return data

class Executor:
    def __init__(self, default_model='MiniMax-M2.1-lightning') -> None:
        load_dotenv()
        
        # Validate required environment variables
        required_env_vars = ["OPENAI_API_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        max_token_model = {'MiniMax-M2.1-lightning':204800, 'MiniMax-M2.1':204800}
        self.token_limit = max_token_model.get(default_model)
        self.prompter = Prompter()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.llm = ChatOpenAI(
            model=default_model, #MiniMax-M2.1-lightning
            temperature=0,
        )
        self.gamma = Gamma()
        self.chroma = Chroma()
        self.polymarket = Polymarket()

    def get_llm_response(self, user_input: str) -> str:
        system_message = SystemMessage(content=str(self.prompter.market_analyst()))
        human_message = HumanMessage(content=user_input)
        messages = [system_message, human_message]
        result = self.llm.invoke(messages)
        return result.content

    def get_superforecast(
        self, event_title: str, market_question: str, outcome: str
    ) -> str:
        messages = self.prompter.superforecaster(
            description=event_title, question=market_question, outcome=outcome
        )
        result = self.llm.invoke(messages)
        return result.content


    def estimate_tokens(self, text: str) -> int:
        # This is a rough estimate. For more accurate results, consider using a tokenizer.
        return len(text) // 4  # Assuming average of 4 characters per token

    def process_data_chunk(self, data1: List[Dict[Any, Any]], data2: List[Dict[Any, Any]], user_input: str) -> str:
        system_message = SystemMessage(
            content=str(self.prompter.prompts_polymarket(data1=data1, data2=data2))
        )
        human_message = HumanMessage(content=user_input)
        messages = [system_message, human_message]
        result = self.llm.invoke(messages)
        return result.content


    def divide_list(self, original_list, i):
        # Calculate the size of each sublist
        sublist_size = math.ceil(len(original_list) / i)
        
        # Use list comprehension to create sublists
        return [original_list[j:j+sublist_size] for j in range(0, len(original_list), sublist_size)]
    
    def get_polymarket_llm(self, user_input: str) -> str:
        data1 = self.gamma.get_current_events()
        data2 = self.gamma.get_current_markets()
        
        combined_data = str(self.prompter.prompts_polymarket(data1=data1, data2=data2))
        
        # Estimate total tokens
        total_tokens = self.estimate_tokens(combined_data)
        
        # Set a token limit (adjust as needed, leaving room for system and user messages)
        token_limit = self.token_limit
        if total_tokens <= token_limit:
            # If within limit, process normally
            return self.process_data_chunk(data1, data2, user_input)
        else:
            # If exceeding limit, process in chunks
            chunk_size = len(combined_data) // ((total_tokens // token_limit) + 1)
            print(f'total tokens {total_tokens} exceeding llm capacity, now will split and answer')
            group_size = (total_tokens // token_limit) + 1 # 3 is safe factor
            keys_no_meaning = ['image','pagerDutyNotificationEnabled','resolvedBy','endDate','clobTokenIds','negRiskMarketID','conditionId','updatedAt','startDate']
            useful_keys = ['id','questionID','description','liquidity','clobTokenIds','outcomes','outcomePrices','volume','startDate','endDate','question','questionID','events']
            data1 = retain_keys(data1, useful_keys)
            cut_1 = self.divide_list(data1, group_size)
            cut_2 = self.divide_list(data2, group_size)
            cut_data_12 = zip(cut_1, cut_2)

            results = []

            for cut_data in cut_data_12:
                sub_data1 = cut_data[0]
                sub_data2 = cut_data[1]
                sub_tokens = self.estimate_tokens(str(self.prompter.prompts_polymarket(data1=sub_data1, data2=sub_data2)))

                result = self.process_data_chunk(sub_data1, sub_data2, user_input)
                results.append(result)
            
            combined_result = " ".join(results)
            
        
            
            return combined_result
    def filter_events(self, events: "list[SimpleEvent]") -> str:
        prompt = self.prompter.filter_events(events)
        result = self.llm.invoke(prompt)
        return result.content

    def filter_events_with_rag(self, events: "list[SimpleEvent]") -> "list[tuple]":
        prompt = self.prompter.filter_events()
        print()
        print("... prompting ... ", prompt)
        print()
        return self.chroma.events(events, prompt)

    def map_filtered_events_to_markets(
        self, filtered_events: "list[tuple]"
    ) -> "list[SimpleMarket]":
        markets = []
        error_stats = {
            "not_active": 0,
            "missing_outcome_prices": 0,
            "missing_clob_token_ids": 0,
            "other_errors": 0,
            "total_market_ids": 0,
            "successful": 0,
            "failed": 0
        }
        
        for idx, event_tuple in enumerate(filtered_events):
            try:
                # filtered_events is a list of tuples from RAG: (Document, score)
                event_doc = event_tuple[0]
                data = json.loads(event_doc.json())
                
                market_ids_str = data.get("metadata", {}).get("markets", "")
                if not market_ids_str:
                    print(f"Warning: Event {idx} has no markets")
                    continue
                    
                market_ids = market_ids_str.split(",")
                error_stats["total_market_ids"] += len(market_ids)
                print(f"Processing event {idx}: {len(market_ids)} markets")
                
                for market_id in market_ids:
                    if not market_id or not market_id.strip():
                        continue
                    try:
                        market_data = self.gamma.get_market(market_id.strip())
                        formatted_market_data = self.polymarket.map_api_to_market(market_data)
                        markets.append(formatted_market_data)
                        error_stats["successful"] += 1
                    except ValueError as ve:
                        error_stats["failed"] += 1
                        error_msg = str(ve)
                        if "not active" in error_msg:
                            error_stats["not_active"] += 1
                        elif "outcomePrices" in error_msg:
                            error_stats["missing_outcome_prices"] += 1
                        elif "CLOB token IDs" in error_msg:
                            error_stats["missing_clob_token_ids"] += 1
                        else:
                            error_stats["other_errors"] += 1
                        print(f"  ✗ Error fetching market {market_id}: {error_msg}")
                    except Exception as e:
                        error_stats["failed"] += 1
                        error_stats["other_errors"] += 1
                        print(f"  ✗ Error fetching market {market_id}: {e}")
            except Exception as event_error:
                print(f"Error processing event {idx}: {event_error}")
                import traceback
                traceback.print_exc()
                continue
        
        # Print summary statistics
        print("\n=== Market Mapping Statistics ===")
        print(f"Total events: {len(filtered_events)}")
        print(f"Events with markets: {len([e for e in filtered_events if e[0].metadata.get('markets')])}")
        print(f"Events without markets: {len(filtered_events) - len([e for e in filtered_events if e[0].metadata.get('markets')])}")
        print(f"Total market IDs to fetch: {error_stats['total_market_ids']}")
        print(f"Successfully fetched: {error_stats['successful']}")
        print(f"Failed to fetch: {error_stats['failed']}")
        print("\nError breakdown:")
        if error_stats['not_active'] > 0:
            print(f"  Not active (filtered out): {error_stats['not_active']}")
        if error_stats['missing_outcome_prices'] > 0:
            print(f"  Missing outcomePrices: {error_stats['missing_outcome_prices']}")
        if error_stats['missing_clob_token_ids'] > 0:
            print(f"  Missing CLOB token IDs: {error_stats['missing_clob_token_ids']}")
        if error_stats['other_errors'] > 0:
            print(f"  Other errors: {error_stats['other_errors']}")
        print(f"Final markets count (active only): {len(markets)}")
        print("==================================================\n")
        
        return markets
        
        return markets

    def filter_markets(self, markets: "list[SimpleMarket]") -> "list[tuple]":
        prompt = self.prompter.filter_markets()
        print()
        print("... prompting ... ", prompt)
        print()
        return self.chroma.markets(markets, prompt)

    def source_best_trade(self, market_object: tuple) -> str:
        market_document = market_object[0].dict()
        market = market_document["metadata"]
        outcome_prices = ast.literal_eval(market["outcome_prices"])
        outcomes = ast.literal_eval(market["outcomes"])
        question = market["question"]
        description = market_document["page_content"]

        prompt = self.prompter.superforecaster(question, description, outcomes)
        print()
        print("... prompting ... ", prompt)
        print()
        result = self.llm.invoke(prompt)
        content = result.content

        print("result: ", content)
        print()
        prompt = self.prompter.one_best_trade(content, outcomes, outcome_prices)
        print("... prompting ... ", prompt)
        print()
        result = self.llm.invoke(prompt)
        content = result.content

        print("result: ", content)
        print()
        return content

    def format_trade_prompt_for_execution(self, best_trade: str) -> float:
        try:
            # Parse the trade format: price:0.5, size:0.1, side:BUY
            lines = best_trade.strip().split('\n')
            size_value = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('size:'):
                    # Extract size value after "size:"
                    size_match = re.search(r'size:\s*([\d.]+)', line)
                    if size_match:
                        size_value = float(size_match.group(1))
                        break
            
            if size_value is None:
                print(f"Warning: Could not parse size from trade: {best_trade}")
                # Try fallback parsing
                size_match = re.search(r'size[:\s]*([\d.]+)', best_trade)
                if size_match:
                    size_value = float(size_match.group(1))
                else:
                    raise ValueError(f"Cannot parse size from: {best_trade}")
            
            usdc_balance = self.polymarket.get_usdc_balance()
            trade_amount = size_value * usdc_balance
            
            print(f"Size: {size_value}, USDC Balance: {usdc_balance}, Trade Amount: {trade_amount}")
            return trade_amount
        except Exception as e:
            print(f"Error parsing trade amount: {e}")
            print(f"Best trade content: {best_trade}")
            raise

    def source_best_market_to_create(self, filtered_markets) -> str:
        prompt = self.prompter.create_new_market(filtered_markets)
        print()
        print("... prompting ... ", prompt)
        print()
        result = self.llm.invoke(prompt)
        content = result.content
        return content
