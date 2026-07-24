from __future__ import annotations

import asyncio
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel

from mongo_database import mongo_database


COLLECTION_NAMES = (
    "conversations",
    "messages",
    "response_versions",
    "feedback",
)


async def create_missing_collections(database: Any) -> None:
    """Create the required collections when they do not exist."""
    existing_collections = set(
        await database.list_collection_names()
    )

    for collection_name in COLLECTION_NAMES:
        if collection_name not in existing_collections:
            await database.create_collection(collection_name)

            print(
                f"Created collection: {collection_name}"
            )


async def create_indexes(database: Any) -> None:
    """Create indexes used by chat history and feedback queries."""

    await database["conversations"].create_indexes(
        [
            IndexModel(
                [
                    ("client_id", ASCENDING),
                    ("updated_at", DESCENDING),
                ],
                name="conversation_history_lookup",
            ),
        ]
    )

    await database["messages"].create_indexes(
        [
            IndexModel(
                [
                    ("conversation_id", ASCENDING),
                    ("created_at", ASCENDING),
                ],
                name="conversation_messages_lookup",
            ),
        ]
    )

    await database["response_versions"].create_indexes(
        [
            IndexModel(
                [
                    ("message_id", ASCENDING),
                    ("version_number", ASCENDING),
                ],
                unique=True,
                name="message_version_unique",
            ),
            IndexModel(
                [
                    ("message_id", ASCENDING),
                    ("created_at", ASCENDING),
                ],
                name="message_versions_lookup",
            ),
        ]
    )

    await database["feedback"].create_indexes(
        [
            IndexModel(
                [
                    ("client_id", ASCENDING),
                    ("version_id", ASCENDING),
                ],
                unique=True,
                name="client_version_feedback_unique",
            ),
            IndexModel(
                [
                    ("message_id", ASCENDING),
                    ("created_at", DESCENDING),
                ],
                name="message_feedback_lookup",
            ),
        ]
    )

    print("MongoDB indexes created successfully.")


async def initialize_mongo_schema(database: Any) -> None:
    """Create all collections and indexes required by the application."""
    await create_missing_collections(database)
    await create_indexes(database)


async def test_schema() -> None:
    """Initialize and inspect the MongoDB schema."""
    await mongo_database.connect()

    if mongo_database.database is None:
        raise RuntimeError(
            "MongoDB database was not initialized."
        )

    await initialize_mongo_schema(
        mongo_database.database
    )

    collections = sorted(
        await mongo_database.database.list_collection_names()
    )

    print(f"Available collections: {collections}")

    for collection_name in COLLECTION_NAMES:
        indexes = await (
            mongo_database.database[collection_name]
            .index_information()
        )

        print(
            f"{collection_name} indexes: "
            f"{list(indexes.keys())}"
        )

    await mongo_database.close()


if __name__ == "__main__":
    asyncio.run(test_schema())