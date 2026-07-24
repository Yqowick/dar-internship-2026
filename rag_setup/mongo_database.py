from __future__ import annotations

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from pymongo import AsyncMongoClient


load_dotenv()


class MongoDatabase:
    """Manage one shared asynchronous MongoDB connection."""

    def __init__(self) -> None:
        self.client: AsyncMongoClient | None = None
        self.database: Any = None

    async def connect(self) -> None:
        """Connect to MongoDB and verify that the server is reachable."""
        mongodb_url = os.getenv("MONGODB_URL")
        database_name = os.getenv("MONGO_DATABASE")

        if not mongodb_url:
            raise RuntimeError(
                "MONGODB_URL is missing from the .env file."
            )

        if not database_name:
            raise RuntimeError(
                "MONGO_DATABASE is missing from the .env file."
            )

        self.client = AsyncMongoClient(
            mongodb_url,
            serverSelectionTimeoutMS=5000,
        )

        await self.client.admin.command("ping")

        self.database = self.client[database_name]

        print(
            f"MongoDB connected successfully: {database_name}"
        )

    async def close(self) -> None:
        """Close the MongoDB connection cleanly."""
        if self.client is not None:
            await self.client.close()

        self.client = None
        self.database = None

        print("MongoDB connection closed.")


mongo_database = MongoDatabase()


async def test_connection() -> None:
    """Allow this module to be tested directly from the terminal."""
    await mongo_database.connect()

    assert mongo_database.database is not None

    collections = await (
        mongo_database.database.list_collection_names()
    )

    print(f"Existing collections: {collections}")

    await mongo_database.close()


if __name__ == "__main__":
    asyncio.run(test_connection())