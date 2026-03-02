"""
Manual integration test for create_content_item_handler.

Usage:
    python scripts/test_create_content_item.py <url>

Example:
    python scripts/test_create_content_item.py https://www.reuters.com/technology/apple-reports-record-earnings
"""

import sys
import json
from pathlib import Path

# Add src to path so imports work without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prometheus_backend.dagger.aws import AWSClients
from prometheus_backend.config import settings
from prometheus_backend.models.content import CreateContentItemRequest
from prometheus_backend.storage.local_file_system.content_item_store import ContentItemStore
from prometheus_backend.handlers.create_content_item_handler import execute


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_create_content_item.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"Source URL: {url}\n")

    print("Initializing AWS clients...")
    aws_clients = AWSClients(region_name=settings.aws_region)
    aws_clients.initialize()
    settings.set_aws_clients(aws_clients)
    print("AWS clients initialized.\n")

    store = ContentItemStore("src/prometheus_backend/data/content_items.jsonl")

    print("Running handler...")
    request = CreateContentItemRequest(source_url=url)
    response = execute(request, store)
    print(f"Done. Created content item ID: {response.id}\n")

    item = store.get(response.id)
    print("Saved content item:")
    print(json.dumps(json.loads(item.model_dump_json()), indent=2))


if __name__ == "__main__":
    main()
