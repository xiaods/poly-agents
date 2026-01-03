import json
import os
import time

from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import JSONLoader
from langchain_community.vectorstores.chroma import Chroma

from agents.polymarket.gamma import GammaMarketClient
from agents.utils.objects import SimpleEvent, SimpleMarket


def get_embedding_function():
    """获取 SiliconFlow Embeddings 函数"""
    api_key = os.getenv("EMBEDDING_API_KEY", "")
    api_base = os.getenv("EMBEDDING_API_BASE", "https://api.siliconflow.cn/v1")
    
    return OpenAIEmbeddings(
        model="Qwen/Qwen3-Embedding-8B",
        base_url=api_base,
        api_key=api_key
    )


class PolymarketRAG:
    def __init__(self, local_db_directory=None, embedding_function=None) -> None:
        self.gamma_client = GammaMarketClient()
        self.local_db_directory = local_db_directory
        self.embedding_function = embedding_function

    def load_json_from_local(
        self, json_file_path=None, vector_db_directory="./local_db"
    ) -> None:
        loader = JSONLoader(
            file_path=json_file_path, jq_schema=".[].description", text_content=False
        )
        loaded_docs = loader.load()

        embedding_function = get_embedding_function()
        Chroma.from_documents(
            loaded_docs, embedding_function, persist_directory=vector_db_directory
        )

    def create_local_markets_rag(self, local_directory="./local_db") -> None:
        all_markets = self.gamma_client.get_all_current_markets()

        if not os.path.isdir(local_directory):
            os.mkdir(local_directory)

        local_file_path = f"{local_directory}/all-current-markets_{time.time()}.json"

        with open(local_file_path, "w+") as output_file:
            json.dump(all_markets, output_file)

        self.load_json_from_local(
            json_file_path=local_file_path, vector_db_directory=local_directory
        )

    def query_local_markets_rag(
        self, local_directory=None, query=None
    ) -> "list[tuple]":
        embedding_function = get_embedding_function()
        local_db = Chroma(
            persist_directory=local_directory, embedding_function=embedding_function
        )
        response_docs = local_db.similarity_search_with_score(query=query)
        return response_docs

    def events(self, events: "list[SimpleEvent]", prompt: str) -> "list[tuple]":
        # create local json file
        local_events_directory: str = "./local_db_events"
        if not os.path.isdir(local_events_directory):
            os.mkdir(local_events_directory)
        local_file_path = f"{local_events_directory}/events.json"
        dict_events = [x.dict() for x in events]
        with open(local_file_path, "w+") as output_file:
            json.dump(dict_events, output_file)

        # create vector db
        def metadata_func(record: dict, metadata: dict) -> dict:

            metadata["id"] = record.get("id")
            metadata["markets"] = record.get("markets")

            return metadata

        loader = JSONLoader(
            file_path=local_file_path,  # Use the file path, not directory
            jq_schema=".[]",
            content_key="description",
            text_content=False,
            metadata_func=metadata_func,
        )
        loaded_docs = loader.load()
        
        # Validate loaded documents
        if not loaded_docs:
            print("Warning: No documents loaded from JSON file")
            return []
        
        print(f"Loaded {len(loaded_docs)} documents for embedding")
        
        # Check for valid description content
        valid_docs = []
        for doc in loaded_docs:
            if doc.page_content and doc.page_content.strip():
                valid_docs.append(doc)
            else:
                print(f"Warning: Document with empty content skipped: {doc.metadata}")
        
        if not valid_docs:
            print("Error: No valid documents with content found")
            return []
        
        print(f"Processing {len(valid_docs)} valid documents for embedding")
        
        try:
            # Use SiliconFlow Embeddings
            embedding_function = get_embedding_function()
            print(f"Using SiliconFlow API: Qwen/Qwen3-Embedding-8B")
            
            # Process in smaller batches to avoid API issues
            batch_size = 10  # Reduce batch size for better stability
            local_db = None
            vector_db_directory = f"{local_events_directory}/chroma"
            
            # Clean up existing database directory if it exists to avoid readonly errors
            import shutil
            if os.path.exists(vector_db_directory):
                try:
                    shutil.rmtree(vector_db_directory)
                    print(f"Cleaned up existing vector database directory: {vector_db_directory}")
                except Exception as cleanup_error:
                    print(f"Warning: Could not clean up vector database directory: {cleanup_error}")
            
            for i in range(0, len(valid_docs), batch_size):
                batch = valid_docs[i:i + batch_size]
                print(f"Processing batch {i//batch_size + 1}/{(len(valid_docs) + batch_size - 1)//batch_size} ({len(batch)} documents)")
                
                try:
                    if local_db is None:
                        # First batch: create the database
                        local_db = Chroma.from_documents(
                            batch, embedding_function, persist_directory=vector_db_directory
                        )
                    else:
                        # Subsequent batches: add to existing database
                        local_db.add_documents(batch)
                    print(f"  ✓ Batch {i//batch_size + 1} completed successfully")
                except Exception as batch_error:
                    print(f"  ✗ Error processing batch {i//batch_size + 1}: {batch_error}")
                    import traceback
                    traceback.print_exc()
                    # Continue with next batch
                    continue
            
            if local_db is None:
                print("Error: Failed to create vector database after all retries")
                return []
            
            print(f"Successfully created vector database with {len(valid_docs)} documents")
            
        except Exception as e:
            print(f"Error creating vector database: {e}")
            import traceback
            traceback.print_exc()
            raise

        # query
        return local_db.similarity_search_with_score(query=prompt)

    def markets(self, markets: "list[SimpleMarket]", prompt: str) -> "list[tuple]":
        # create local json file
        local_events_directory: str = "./local_db_markets"
        if not os.path.isdir(local_events_directory):
            os.mkdir(local_events_directory)
        local_file_path = f"{local_events_directory}/markets.json"
        with open(local_file_path, "w+") as output_file:
            json.dump(markets, output_file)

        # create vector db
        def metadata_func(record: dict, metadata: dict) -> dict:

            metadata["id"] = record.get("id")
            metadata["outcomes"] = record.get("outcomes")
            metadata["outcome_prices"] = record.get("outcome_prices")
            metadata["question"] = record.get("question")
            metadata["clob_token_ids"] = record.get("clob_token_ids")

            return metadata

        loader = JSONLoader(
            file_path=local_file_path,
            jq_schema=".[]",
            content_key="description",
            text_content=False,
            metadata_func=metadata_func,
        )
        loaded_docs = loader.load()
        
        # Validate loaded documents
        if not loaded_docs:
            print("Warning: No documents loaded from JSON file")
            return []
        
        print(f"Loaded {len(loaded_docs)} documents for embedding")
        
        # Check for valid description content
        valid_docs = []
        for doc in loaded_docs:
            if doc.page_content and doc.page_content.strip():
                valid_docs.append(doc)
            else:
                print(f"Warning: Document with empty content skipped: {doc.metadata}")
        
        if not valid_docs:
            print("Error: No valid documents with content found")
            return []
        
        print(f"Processing {len(valid_docs)} valid documents for embedding")
        
        try:
            # Use SiliconFlow Embeddings
            embedding_function = get_embedding_function()
            print(f"Using SiliconFlow API: Qwen/Qwen3-Embedding-8B")
            
            # Process in smaller batches to avoid API issues
            batch_size = 10  # Reduce batch size for better stability
            local_db = None
            vector_db_directory = f"{local_events_directory}/chroma"
            
            # Clean up existing database directory if it exists to avoid readonly errors
            import shutil
            if os.path.exists(vector_db_directory):
                try:
                    shutil.rmtree(vector_db_directory)
                    print(f"Cleaned up existing vector database directory: {vector_db_directory}")
                except Exception as cleanup_error:
                    print(f"Warning: Could not clean up vector database directory: {cleanup_error}")
            
            for i in range(0, len(valid_docs), batch_size):
                batch = valid_docs[i:i + batch_size]
                print(f"Processing batch {i//batch_size + 1}/{(len(valid_docs) + batch_size - 1)//batch_size} ({len(batch)} documents)")
                
                try:
                    if local_db is None:
                        # First batch: create the database
                        local_db = Chroma.from_documents(
                            batch, embedding_function, persist_directory=vector_db_directory
                        )
                    else:
                        # Subsequent batches: add to existing database
                        local_db.add_documents(batch)
                    print(f"  ✓ Batch {i//batch_size + 1} completed successfully")
                except Exception as batch_error:
                    print(f"  ✗ Error processing batch {i//batch_size + 1}: {batch_error}")
                    import traceback
                    traceback.print_exc()
                    # Continue with next batch
                    continue
            
            if local_db is None:
                print("Error: Failed to create vector database after all retries")
                return []
            
            print(f"Successfully created vector database with {len(valid_docs)} documents")
            
        except Exception as e:
            print(f"Error creating vector database: {e}")
            import traceback
            traceback.print_exc()
            raise

        # query
        return local_db.similarity_search_with_score(query=prompt)
