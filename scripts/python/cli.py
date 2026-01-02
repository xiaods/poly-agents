import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import typer
from devtools import pprint

from agents.polymarket.polymarket import Polymarket
from agents.connectors.chroma import PolymarketRAG
from agents.connectors.news import News
from agents.application.trade import Trader
from agents.application.executor import Executor
from agents.application.creator import Creator

app = typer.Typer()
polymarket = Polymarket()
newsapi_client = News()
polymarket_rag = PolymarketRAG()


@app.command()
def get_all_markets(limit: int = 5, sort_by: str = "spread") -> None:
    """
    Query Polymarket's markets
    """
    print(f"limit: int = {limit}, sort_by: str = {sort_by}")
    markets = polymarket.get_all_markets()
    markets = polymarket.filter_markets_for_trading(markets)
    if sort_by == "spread":
        markets = sorted(markets, key=lambda x: x.spread, reverse=True)
    markets = markets[:limit]
    pprint(markets)


@app.command()
def get_relevant_news(keywords: str) -> None:
    """
    Use NewsAPI to query the internet
    """
    articles = newsapi_client.get_articles_for_cli_keywords(keywords)
    pprint(articles)


@app.command()
def get_all_events(limit: int = 5, sort_by: str = "number_of_markets", fetch_limit: int = 100, max_fetch: int = None) -> None:
    """
    Query Polymarket's events
    
    Args:
        limit: Maximum number of events to return in final result
        sort_by: Sort by "number_of_markets" or other criteria
        fetch_limit: Number of events to fetch per API request (default: 100)
        max_fetch: Maximum total number of events to fetch from API. 
                   If None, defaults to fetch_limit (only one request).
                   Set to a larger value to fetch more events with pagination.
    """
    # Default to only one request if max_fetch is not specified
    if max_fetch is None:
        max_fetch = fetch_limit
    
    print(f"limit: int = {limit}, sort_by: str = {sort_by}, fetch_limit: int = {fetch_limit}, max_fetch: {max_fetch}")
    # Get tradeable events using API-level filtering with pagination
    events = polymarket.get_all_events(tradeable_only=True, limit=fetch_limit, max_events=max_fetch)
    print(f"Retrieved {len(events)} events from API (pre-filtered for tradeable)")
    # Additional client-side filtering for restricted events (API doesn't support restricted parameter)
    events = polymarket.filter_events_for_trading(events)
    print(f"After filtering: {len(events)} tradeable events")
    
    if sort_by == "number_of_markets":
        # markets is a comma-separated string, count the number of markets
        events = sorted(events, key=lambda x: len(x.markets.split(',')) if x.markets else 0, reverse=True)
    
    events = events[:limit]
    print(f"Final result: {len(events)} events")
    print("\n=== Events ===")
    pprint(events)


@app.command()
def create_local_markets_rag(local_directory: str) -> None:
    """
    Create a local markets database for RAG
    """
    polymarket_rag.create_local_markets_rag(local_directory=local_directory)


@app.command()
def query_local_markets_rag(vector_db_directory: str, query: str) -> None:
    """
    RAG over a local database of Polymarket's events
    """
    response = polymarket_rag.query_local_markets_rag(
        local_directory=vector_db_directory, query=query
    )
    pprint(response)


@app.command()
def ask_superforecaster(event_title: str, market_question: str, outcome: str) -> None:
    """
    Ask a superforecaster about a trade
    """
    print(
        f"event: str = {event_title}, question: str = {market_question}, outcome (usually yes or no): str = {outcome}"
    )
    executor = Executor()
    response = executor.get_superforecast(
        event_title=event_title, market_question=market_question, outcome=outcome
    )
    print(f"Response:{response}")


@app.command()
def create_market() -> None:
    """
    Format a request to create a market on Polymarket
    """
    c = Creator()
    market_description = c.one_best_market()
    print(f"market_description: str = {market_description}")


@app.command()
def ask_llm(user_input: str) -> None:
    """
    Ask a question to the LLM and get a response.
    """
    executor = Executor()
    response = executor.get_llm_response(user_input)
    print(f"LLM Response: {response}")


@app.command()
def ask_polymarket_llm(user_input: str) -> None:
    """
    What types of markets do you want trade?
    """
    executor = Executor()
    response = executor.get_polymarket_llm(user_input=user_input)
    print(f"LLM + current markets&events response: {response}")


@app.command()
def run_autonomous_trader() -> None:
    """
    Let an autonomous system trade for you.
    """
    trader = Trader()
    trader.one_best_trade()


if __name__ == "__main__":
    app()
