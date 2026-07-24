from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING


CLIENT_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{8,128}$"
)

ALLOWED_FINAL_STATUSES = {
    "complete",
    "stopped",
    "error",
}


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def iso_datetime(value: datetime | None) -> str:
    """Convert a MongoDB datetime into an ISO-8601 UTC string."""
    if value is None:
        value = utc_now()

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    ).isoformat()


def validate_client_id(client_id: str) -> str:
    """Validate the anonymous browser identifier used to own chats."""
    cleaned = client_id.strip()

    if not CLIENT_ID_PATTERN.fullmatch(
        cleaned
    ):
        raise ValueError(
            "client_id must contain 8-128 letters, "
            "numbers, underscores, or hyphens."
        )

    return cleaned


def parse_object_id(
    value: str,
    field_name: str,
) -> ObjectId:
    """Convert a public string identifier into a MongoDB ObjectId."""
    if not ObjectId.is_valid(value):
        raise ValueError(
            f"Invalid {field_name}."
        )

    return ObjectId(value)


def create_conversation_title(
    question: str,
) -> str:
    """Create a short chat title from the first user question."""
    cleaned = re.sub(
        r"\s+",
        " ",
        question,
    ).strip()

    cleaned = re.sub(
        r"[?!.]+$",
        "",
        cleaned,
    )

    if not cleaned:
        return "New conversation"

    if len(cleaned) <= 52:
        return cleaned

    return f"{cleaned[:49].rstrip()}…"


class ChatRepository:
    """MongoDB persistence for chats and response-version history."""

    def __init__(
        self,
        database: Any,
    ) -> None:
        self.database = database
        self.conversations = database[
            "conversations"
        ]
        self.messages = database[
            "messages"
        ]
        self.response_versions = database[
            "response_versions"
        ]
        self.feedback = database[
            "feedback"
        ]

    def _conversation_summary(
        self,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """Serialize one MongoDB conversation for the API."""
        return {
            "id": str(document["_id"]),
            "title": str(
                document.get(
                    "title",
                    "New conversation",
                )
            ),
            "created_at": iso_datetime(
                document.get("created_at")
            ),
            "updated_at": iso_datetime(
                document.get("updated_at")
            ),
            "message_count": int(
                document.get(
                    "message_count",
                    0,
                )
            ),
            "last_message_preview": str(
                document.get(
                    "last_message_preview",
                    "",
                )
            ),
        }

    def _message_response(
        self,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """Serialize one MongoDB message for the API."""
        active_version_id = document.get(
            "active_version_id"
        )
        version_count = int(
            document.get(
                "version_count",
                0,
            )
        )
        active_version_number = document.get(
            "active_version_number"
        )

        if (
            active_version_number is None
            and active_version_id is not None
            and version_count > 0
        ):
            active_version_number = version_count

        return {
            "id": str(document["_id"]),
            "role": str(
                document.get(
                    "role",
                    "assistant",
                )
            ),
            "content": str(
                document.get(
                    "content",
                    "",
                )
            ),
            "status": str(
                document.get(
                    "status",
                    "complete",
                )
            ),
            "refused": bool(
                document.get(
                    "refused",
                    False,
                )
            ),
            "sources": list(
                document.get(
                    "sources",
                    [],
                )
            ),
            "active_version_id": (
                str(active_version_id)
                if active_version_id is not None
                else None
            ),
            "active_version_number": (
                int(active_version_number)
                if active_version_number is not None
                else None
            ),
            "version_count": version_count,
            "created_at": iso_datetime(
                document.get("created_at")
            ),
            "updated_at": iso_datetime(
                document.get("updated_at")
            ),
        }

    def _version_response(
        self,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """Serialize one response-version document for the API."""
        return {
            "id": str(document["_id"]),
            "message_id": str(
                document["message_id"]
            ),
            "version_number": int(
                document.get(
                    "version_number",
                    1,
                )
            ),
            "content": str(
                document.get(
                    "content",
                    "",
                )
            ),
            "status": str(
                document.get(
                    "status",
                    "complete",
                )
            ),
            "refused": bool(
                document.get(
                    "refused",
                    False,
                )
            ),
            "sources": list(
                document.get(
                    "sources",
                    [],
                )
            ),
            "created_at": iso_datetime(
                document.get("created_at")
            ),
        }

    async def list_conversations(
        self,
        client_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List one browser client's conversations, newest first."""
        validated_client_id = validate_client_id(
            client_id
        )
        safe_limit = max(
            1,
            min(limit, 200),
        )

        cursor = (
            self.conversations.find(
                {
                    "client_id": validated_client_id
                }
            )
            .sort(
                "updated_at",
                DESCENDING,
            )
            .limit(safe_limit)
        )
        documents = await cursor.to_list(
            length=safe_limit
        )

        return [
            self._conversation_summary(
                document
            )
            for document in documents
        ]

    async def get_conversation(
        self,
        client_id: str,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        """Load one owned conversation and all of its messages."""
        validated_client_id = validate_client_id(
            client_id
        )
        conversation_object_id = parse_object_id(
            conversation_id,
            "conversation ID",
        )

        conversation = await self.conversations.find_one(
            {
                "_id": conversation_object_id,
                "client_id": validated_client_id,
            }
        )

        if conversation is None:
            return None

        cursor = self.messages.find(
            {
                "conversation_id": conversation_object_id,
                "client_id": validated_client_id,
            }
        ).sort(
            [
                ("created_at", ASCENDING),
                ("_id", ASCENDING),
            ]
        )
        message_documents = await cursor.to_list(
            length=None
        )

        return {
            **self._conversation_summary(
                conversation
            ),
            "messages": [
                self._message_response(
                    document
                )
                for document in message_documents
            ],
        }

    async def start_exchange(
        self,
        client_id: str,
        question: str,
        conversation_id: str | None,
    ) -> dict[str, Any]:
        """Create or reuse a conversation and store two message shells."""
        validated_client_id = validate_client_id(
            client_id
        )
        now = utc_now()

        if conversation_id is None:
            conversation_document = {
                "client_id": validated_client_id,
                "title": create_conversation_title(
                    question
                ),
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
                "last_message_preview": question[:160],
            }
            result = await self.conversations.insert_one(
                conversation_document
            )
            conversation_document["_id"] = result.inserted_id
        else:
            conversation_object_id = parse_object_id(
                conversation_id,
                "conversation ID",
            )
            conversation_document = await self.conversations.find_one(
                {
                    "_id": conversation_object_id,
                    "client_id": validated_client_id,
                }
            )

            if conversation_document is None:
                raise LookupError(
                    "Conversation not found."
                )

        conversation_object_id = conversation_document[
            "_id"
        ]

        user_document = {
            "conversation_id": conversation_object_id,
            "client_id": validated_client_id,
            "role": "user",
            "content": question,
            "status": "complete",
            "refused": False,
            "sources": [],
            "active_version_id": None,
            "active_version_number": None,
            "version_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        user_result = await self.messages.insert_one(
            user_document
        )
        user_document["_id"] = user_result.inserted_id

        assistant_document = {
            "conversation_id": conversation_object_id,
            "client_id": validated_client_id,
            "role": "assistant",
            "content": "",
            "status": "streaming",
            "refused": False,
            "sources": [],
            "active_version_id": None,
            "active_version_number": None,
            "version_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        assistant_result = await self.messages.insert_one(
            assistant_document
        )
        assistant_document["_id"] = assistant_result.inserted_id

        await self.conversations.update_one(
            {"_id": conversation_object_id},
            {
                "$set": {
                    "updated_at": now,
                    "last_message_preview": question[:160],
                },
                "$inc": {
                    "message_count": 2,
                },
            },
        )

        conversation_document["updated_at"] = now
        conversation_document["message_count"] = int(
            conversation_document.get(
                "message_count",
                0,
            )
        ) + 2
        conversation_document[
            "last_message_preview"
        ] = question[:160]

        return {
            "conversation": self._conversation_summary(
                conversation_document
            ),
            "user_message": self._message_response(
                user_document
            ),
            "assistant_message": self._message_response(
                assistant_document
            ),
        }

    async def _owned_assistant_message(
        self,
        client_id: str,
        message_id: str,
        conversation_id: str | None = None,
    ) -> tuple[str, ObjectId, dict[str, Any]]:
        """Validate ownership and return an assistant message."""
        validated_client_id = validate_client_id(
            client_id
        )
        message_object_id = parse_object_id(
            message_id,
            "message ID",
        )
        query: dict[str, Any] = {
            "_id": message_object_id,
            "client_id": validated_client_id,
            "role": "assistant",
        }

        if conversation_id is not None:
            query["conversation_id"] = parse_object_id(
                conversation_id,
                "conversation ID",
            )

        message = await self.messages.find_one(
            query
        )

        if message is None:
            raise LookupError(
                "Assistant message not found."
            )

        return (
            validated_client_id,
            message_object_id,
            message,
        )

    async def finish_assistant_message(
        self,
        client_id: str,
        conversation_id: str,
        assistant_message_id: str,
        content: str,
        status: str,
        refused: bool,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Store an initial assistant answer and response version."""
        if status not in ALLOWED_FINAL_STATUSES:
            raise ValueError(
                "Invalid assistant message status."
            )

        (
            validated_client_id,
            message_object_id,
            assistant_message,
        ) = await self._owned_assistant_message(
            client_id=client_id,
            message_id=assistant_message_id,
            conversation_id=conversation_id,
        )
        conversation_object_id = parse_object_id(
            conversation_id,
            "conversation ID",
        )
        now = utc_now()
        cleaned_content = content.strip()

        if status == "stopped" and not cleaned_content:
            cleaned_content = "Response stopped."

        version_id: ObjectId | None = None
        version_number: int | None = None

        if (
            status in {"complete", "stopped"}
            and cleaned_content
        ):
            version_number = int(
                assistant_message.get(
                    "version_count",
                    0,
                )
            ) + 1
            version_document = {
                "conversation_id": conversation_object_id,
                "message_id": message_object_id,
                "version_number": version_number,
                "content": cleaned_content,
                "status": status,
                "refused": refused,
                "sources": sources,
                "created_at": now,
            }
            version_result = await self.response_versions.insert_one(
                version_document
            )
            version_id = version_result.inserted_id

        message_updates: dict[str, Any] = {
            "content": cleaned_content,
            "status": status,
            "refused": refused,
            "sources": sources,
            "updated_at": now,
        }

        if version_id is not None:
            message_updates.update(
                {
                    "active_version_id": version_id,
                    "active_version_number": version_number,
                    "version_count": version_number,
                }
            )

        await self.messages.update_one(
            {
                "_id": message_object_id,
                "conversation_id": conversation_object_id,
                "client_id": validated_client_id,
            },
            {"$set": message_updates},
        )

        preview = cleaned_content or "Response failed."
        await self.conversations.update_one(
            {
                "_id": conversation_object_id,
                "client_id": validated_client_id,
            },
            {
                "$set": {
                    "updated_at": now,
                    "last_message_preview": preview[:160],
                }
            },
        )

        return {
            "version_id": (
                str(version_id)
                if version_id is not None
                else None
            ),
            "version_number": version_number,
            "version_count": (
                version_number
                if version_number is not None
                else int(
                    assistant_message.get(
                        "version_count",
                        0,
                    )
                )
            ),
        }

    async def prepare_regeneration(
        self,
        client_id: str,
        conversation_id: str,
        assistant_message_id: str,
    ) -> dict[str, Any]:
        """Load the original user question for one assistant response."""
        (
            validated_client_id,
            message_object_id,
            assistant_message,
        ) = await self._owned_assistant_message(
            client_id=client_id,
            message_id=assistant_message_id,
            conversation_id=conversation_id,
        )
        conversation_object_id = parse_object_id(
            conversation_id,
            "conversation ID",
        )
        created_at = assistant_message.get(
            "created_at"
        )

        previous_query: dict[str, Any] = {
            "conversation_id": conversation_object_id,
            "client_id": validated_client_id,
            "role": "user",
        }

        if created_at is not None:
            previous_query["$or"] = [
                {
                    "created_at": {
                        "$lt": created_at
                    }
                },
                {
                    "created_at": created_at,
                    "_id": {
                        "$lt": message_object_id
                    },
                },
            ]
        else:
            previous_query["_id"] = {
                "$lt": message_object_id
            }

        cursor = self.messages.find(
            previous_query
        ).sort(
            [
                ("created_at", DESCENDING),
                ("_id", DESCENDING),
            ]
        ).limit(1)
        previous_messages = await cursor.to_list(
            length=1
        )

        if not previous_messages:
            raise LookupError(
                "The original user question was not found."
            )

        return {
            "question": str(
                previous_messages[0].get(
                    "content",
                    "",
                )
            ),
            "assistant_message": self._message_response(
                assistant_message
            ),
        }

    async def finish_regeneration(
        self,
        client_id: str,
        conversation_id: str,
        assistant_message_id: str,
        content: str,
        status: str,
        refused: bool,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Save a regenerated answer as a new selectable version."""
        if status not in ALLOWED_FINAL_STATUSES:
            raise ValueError(
                "Invalid assistant message status."
            )

        (
            validated_client_id,
            message_object_id,
            assistant_message,
        ) = await self._owned_assistant_message(
            client_id=client_id,
            message_id=assistant_message_id,
            conversation_id=conversation_id,
        )
        conversation_object_id = parse_object_id(
            conversation_id,
            "conversation ID",
        )
        cleaned_content = content.strip()

        if (
            status == "error"
            or not cleaned_content
        ):
            return {
                "version_id": (
                    str(
                        assistant_message.get(
                            "active_version_id"
                        )
                    )
                    if assistant_message.get(
                        "active_version_id"
                    ) is not None
                    else None
                ),
                "version_number": assistant_message.get(
                    "active_version_number"
                ) or assistant_message.get(
                    "version_count"
                ),
                "version_count": int(
                    assistant_message.get(
                        "version_count",
                        0,
                    )
                ),
            }

        now = utc_now()
        version_number = int(
            assistant_message.get(
                "version_count",
                0,
            )
        ) + 1
        version_document = {
            "conversation_id": conversation_object_id,
            "message_id": message_object_id,
            "version_number": version_number,
            "content": cleaned_content,
            "status": status,
            "refused": refused,
            "sources": sources,
            "created_at": now,
        }
        version_result = await self.response_versions.insert_one(
            version_document
        )
        version_id = version_result.inserted_id

        await self.messages.update_one(
            {
                "_id": message_object_id,
                "conversation_id": conversation_object_id,
                "client_id": validated_client_id,
            },
            {
                "$set": {
                    "content": cleaned_content,
                    "status": status,
                    "refused": refused,
                    "sources": sources,
                    "active_version_id": version_id,
                    "active_version_number": version_number,
                    "version_count": version_number,
                    "updated_at": now,
                }
            },
        )
        await self.conversations.update_one(
            {
                "_id": conversation_object_id,
                "client_id": validated_client_id,
            },
            {
                "$set": {
                    "updated_at": now,
                    "last_message_preview": cleaned_content[:160],
                }
            },
        )

        return {
            "version_id": str(version_id),
            "version_number": version_number,
            "version_count": version_number,
        }

    async def list_response_versions(
        self,
        client_id: str,
        assistant_message_id: str,
    ) -> dict[str, Any]:
        """Return every saved answer version for one owned message."""
        (
            _,
            message_object_id,
            assistant_message,
        ) = await self._owned_assistant_message(
            client_id=client_id,
            message_id=assistant_message_id,
        )
        cursor = self.response_versions.find(
            {
                "message_id": message_object_id
            }
        ).sort(
            "version_number",
            ASCENDING,
        )
        documents = await cursor.to_list(
            length=None
        )

        active_version_id = assistant_message.get(
            "active_version_id"
        )
        active_version_number = assistant_message.get(
            "active_version_number"
        )
        version_count = int(
            assistant_message.get(
                "version_count",
                len(documents),
            )
        )

        if (
            active_version_number is None
            and active_version_id is not None
        ):
            active_document = next(
                (
                    document
                    for document in documents
                    if document["_id"]
                    == active_version_id
                ),
                None,
            )
            if active_document is not None:
                active_version_number = int(
                    active_document.get(
                        "version_number",
                        version_count,
                    )
                )

        return {
            "message_id": str(message_object_id),
            "active_version_id": (
                str(active_version_id)
                if active_version_id is not None
                else None
            ),
            "active_version_number": (
                int(active_version_number)
                if active_version_number is not None
                else None
            ),
            "version_count": version_count,
            "versions": [
                self._version_response(
                    document
                )
                for document in documents
            ],
        }

    async def activate_response_version(
        self,
        client_id: str,
        assistant_message_id: str,
        version_number: int,
    ) -> dict[str, Any]:
        """Select one saved version and mirror it onto the chat message."""
        if version_number < 1:
            raise ValueError(
                "version_number must be at least 1."
            )

        (
            validated_client_id,
            message_object_id,
            assistant_message,
        ) = await self._owned_assistant_message(
            client_id=client_id,
            message_id=assistant_message_id,
        )
        version_document = await self.response_versions.find_one(
            {
                "message_id": message_object_id,
                "version_number": version_number,
            }
        )

        if version_document is None:
            raise LookupError(
                "Response version not found."
            )

        now = utc_now()
        await self.messages.update_one(
            {"_id": message_object_id},
            {
                "$set": {
                    "content": version_document.get(
                        "content",
                        "",
                    ),
                    "status": version_document.get(
                        "status",
                        "complete",
                    ),
                    "refused": bool(
                        version_document.get(
                            "refused",
                            False,
                        )
                    ),
                    "sources": list(
                        version_document.get(
                            "sources",
                            [],
                        )
                    ),
                    "active_version_id": version_document[
                        "_id"
                    ],
                    "active_version_number": version_number,
                    "updated_at": now,
                }
            },
        )
        conversation_object_id = assistant_message[
            "conversation_id"
        ]
        await self.conversations.update_one(
            {
                "_id": conversation_object_id,
                "client_id": validated_client_id,
            },
            {
                "$set": {
                    "updated_at": now,
                    "last_message_preview": str(
                        version_document.get(
                            "content",
                            "",
                        )
                    )[:160],
                }
            },
        )

        updated_message = await self.messages.find_one(
            {"_id": message_object_id}
        )

        if updated_message is None:
            raise LookupError(
                "Assistant message not found after version activation."
            )

        return self._message_response(
            updated_message
        )

    def _feedback_response(
        self,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """Serialize one feedback document for the API."""
        return {
            "id": str(document["_id"]),
            "client_id": str(document["client_id"]),
            "conversation_id": str(document["conversation_id"]),
            "message_id": str(document["message_id"]),
            "version_id": str(document["version_id"]),
            "version_number": int(document["version_number"]),
            "rating": str(document["rating"]),
            "reason": document.get("reason"),
            "comment": document.get("comment"),
            "created_at": iso_datetime(document.get("created_at")),
            "updated_at": iso_datetime(document.get("updated_at")),
        }

    async def _owned_response_version(
        self,
        client_id: str,
        assistant_message_id: str,
        version_number: int,
    ) -> tuple[str, ObjectId, dict[str, Any], dict[str, Any]]:
        """Validate ownership and return an assistant message and version."""
        if version_number < 1:
            raise ValueError(
                "version_number must be at least 1."
            )

        (
            validated_client_id,
            message_object_id,
            assistant_message,
        ) = await self._owned_assistant_message(
            client_id=client_id,
            message_id=assistant_message_id,
        )

        version_document = await self.response_versions.find_one(
            {
                "message_id": message_object_id,
                "version_number": version_number,
            }
        )

        if version_document is None:
            raise LookupError(
                "Response version not found."
            )

        return (
            validated_client_id,
            message_object_id,
            assistant_message,
            version_document,
        )

    async def get_feedback(
        self,
        client_id: str,
        assistant_message_id: str,
        version_number: int,
    ) -> dict[str, Any] | None:
        """Load this browser's rating for one exact response version."""
        (
            validated_client_id,
            _,
            _,
            version_document,
        ) = await self._owned_response_version(
            client_id=client_id,
            assistant_message_id=assistant_message_id,
            version_number=version_number,
        )

        feedback_document = await self.feedback.find_one(
            {
                "client_id": validated_client_id,
                "version_id": version_document["_id"],
            }
        )

        if feedback_document is None:
            return None

        return self._feedback_response(
            feedback_document
        )

    async def upsert_feedback(
        self,
        client_id: str,
        assistant_message_id: str,
        version_number: int,
        rating: str,
        reason: str | None,
        comment: str | None,
    ) -> dict[str, Any]:
        """Save one rating per browser and response version."""
        if rating not in {"up", "down"}:
            raise ValueError(
                "rating must be either 'up' or 'down'."
            )

        if rating == "down" and not reason:
            raise ValueError(
                "A reason is required for thumbs-down feedback."
            )

        (
            validated_client_id,
            message_object_id,
            assistant_message,
            version_document,
        ) = await self._owned_response_version(
            client_id=client_id,
            assistant_message_id=assistant_message_id,
            version_number=version_number,
        )

        now = utc_now()
        normalized_reason = (
            reason if rating == "down" else None
        )
        normalized_comment = (
            comment.strip()
            if rating == "down" and comment and comment.strip()
            else None
        )

        feedback_filter = {
            "client_id": validated_client_id,
            "version_id": version_document["_id"],
        }

        await self.feedback.update_one(
            feedback_filter,
            {
                "$set": {
                    "conversation_id": assistant_message["conversation_id"],
                    "message_id": message_object_id,
                    "version_id": version_document["_id"],
                    "version_number": version_number,
                    "rating": rating,
                    "reason": normalized_reason,
                    "comment": normalized_comment,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "client_id": validated_client_id,
                    "created_at": now,
                },
            },
            upsert=True,
        )

        feedback_document = await self.feedback.find_one(
            feedback_filter
        )

        if feedback_document is None:
            raise RuntimeError(
                "Feedback could not be saved."
            )

        return self._feedback_response(
            feedback_document
        )

    async def delete_conversation(
        self,
        client_id: str,
        conversation_id: str,
    ) -> bool:
        """Delete one owned conversation and all related records."""
        validated_client_id = validate_client_id(
            client_id
        )
        conversation_object_id = parse_object_id(
            conversation_id,
            "conversation ID",
        )
        conversation = await self.conversations.find_one(
            {
                "_id": conversation_object_id,
                "client_id": validated_client_id,
            },
            {"_id": 1},
        )

        if conversation is None:
            return False

        message_cursor = self.messages.find(
            {
                "conversation_id": conversation_object_id,
                "client_id": validated_client_id,
            },
            {"_id": 1},
        )
        message_documents = await message_cursor.to_list(
            length=None
        )
        message_ids = [
            document["_id"]
            for document in message_documents
        ]

        if message_ids:
            await self.feedback.delete_many(
                {
                    "message_id": {
                        "$in": message_ids
                    }
                }
            )
            await self.response_versions.delete_many(
                {
                    "message_id": {
                        "$in": message_ids
                    }
                }
            )

        await self.messages.delete_many(
            {
                "conversation_id": conversation_object_id,
                "client_id": validated_client_id,
            }
        )
        result = await self.conversations.delete_one(
            {
                "_id": conversation_object_id,
                "client_id": validated_client_id,
            }
        )

        return result.deleted_count == 1
