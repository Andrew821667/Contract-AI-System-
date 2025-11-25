# -*- coding: utf-8 -*-
"""
ChromaDB Client Helper
Supports both HTTP (Docker) and local (embedded) modes
"""
import os
from typing import Optional
from loguru import logger

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not installed")


def get_chroma_client(
    mode: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    persist_directory: Optional[str] = None
):
    """
    Get ChromaDB client based on configuration

    Args:
        mode: 'http' for Docker, 'local' for embedded (default: from env)
        host: ChromaDB host (default: from env or 'localhost')
        port: ChromaDB port (default: from env or 8001)
        persist_directory: Directory for local mode (default: from env)

    Returns:
        ChromaDB client instance

    Example:
        # HTTP mode (Docker)
        client = get_chroma_client(mode='http', host='localhost', port=8001)

        # Local mode (embedded)
        client = get_chroma_client(mode='local', persist_directory='./chroma_data')

        # Auto mode (from environment)
        client = get_chroma_client()
    """
    if not CHROMA_AVAILABLE:
        raise ImportError("ChromaDB not installed. Install with: pip install chromadb")

    # Get configuration from environment if not provided
    mode = mode or os.getenv('CHROMA_MODE', 'http')
    host = host or os.getenv('CHROMA_HOST', 'localhost')
    port = port or int(os.getenv('CHROMA_PORT', '8001'))
    persist_directory = persist_directory or os.getenv('CHROMA_PERSIST_DIRECTORY', './chroma_data')

    logger.info(f"🔌 Connecting to ChromaDB in {mode.upper()} mode...")

    if mode.lower() == 'http':
        # HTTP mode - connect to Docker container
        try:
            client = chromadb.HttpClient(
                host=host,
                port=port,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # Test connection
            client.heartbeat()
            logger.info(f"✅ Connected to ChromaDB at http://{host}:{port}")
            return client

        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB at http://{host}:{port}: {e}")
            logger.info("💡 Tip: Start ChromaDB Docker with: docker-compose up -d chromadb")
            raise

    elif mode.lower() == 'local':
        # Local mode - embedded ChromaDB
        try:
            # Create directory if it doesn't exist
            os.makedirs(persist_directory, exist_ok=True)

            client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            logger.info(f"✅ ChromaDB initialized locally at {persist_directory}")
            return client

        except Exception as e:
            logger.error(f"❌ Failed to initialize local ChromaDB: {e}")
            raise

    else:
        raise ValueError(f"Invalid CHROMA_MODE: {mode}. Use 'http' or 'local'")


def get_or_create_collection(client, name: str, metadata: Optional[dict] = None):
    """
    Get or create a ChromaDB collection

    Args:
        client: ChromaDB client
        name: Collection name
        metadata: Optional collection metadata

    Returns:
        Collection instance
    """
    try:
        collection = client.get_or_create_collection(
            name=name,
            metadata=metadata or {"description": f"Collection: {name}"}
        )
        logger.info(f"📚 Collection '{name}' ready (count: {collection.count()})")
        return collection
    except Exception as e:
        logger.error(f"❌ Failed to get/create collection '{name}': {e}")
        raise


# Example usage
if __name__ == "__main__":
    # Test connection
    client = get_chroma_client()

    # Create test collection
    collection = get_or_create_collection(client, "test")

    print(f"✅ ChromaDB is working!")
    print(f"📊 Collections: {client.list_collections()}")
