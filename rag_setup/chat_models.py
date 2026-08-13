from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StoredSourceResponse(BaseModel):
    """Source metadata stored with one assistant response version."""

    source_id: int
    chunk_id: str
    source_document: str
    section_title: str
    page_number: int | None
    end_page_number: int | None
    snippet: str | None = None


class StoredMessageResponse(BaseModel):
    """One persisted user or assistant message."""

    id: str
    role: str
    content: str
    status: str
    refused: bool
    sources: list[StoredSourceResponse]
    active_version_id: str | None
    active_version_number: int | None
    version_count: int
    created_at: str
    updated_at: str


class ConversationSummaryResponse(BaseModel):
    """Small conversation record used by the chat-history sidebar."""

    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    last_message_preview: str


class ConversationDetailResponse(ConversationSummaryResponse):
    """A conversation and all messages required to resume it."""

    messages: list[StoredMessageResponse]


class ConversationListResponse(BaseModel):
    """Conversation list returned for one anonymous browser client."""

    conversations: list[ConversationSummaryResponse]


class DeleteConversationResponse(BaseModel):
    """Deletion confirmation returned to the frontend."""

    deleted: bool
    conversation_id: str


class PersistedTurnResponse(BaseModel):
    """Identifiers created before an answer begins streaming."""

    conversation: ConversationSummaryResponse
    user_message: StoredMessageResponse
    assistant_message: StoredMessageResponse


class ConversationClientQuery(BaseModel):
    """Reusable validation rules for an anonymous client identifier."""

    client_id: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )


class RegenerateRequest(BaseModel):
    """Request to regenerate one existing assistant message."""

    client_id: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )
    conversation_id: str


class ResponseVersionResponse(BaseModel):
    """One stored alternative answer for an assistant message."""

    id: str
    message_id: str
    version_number: int
    content: str
    status: str
    refused: bool
    sources: list[StoredSourceResponse]
    created_at: str


class ResponseVersionListResponse(BaseModel):
    """All answer versions belonging to one assistant message."""

    message_id: str
    active_version_id: str | None
    active_version_number: int | None
    version_count: int
    versions: list[ResponseVersionResponse]


FeedbackRating = Literal["up", "down"]
FeedbackReason = Literal[
    "incorrect_answer",
    "missing_information",
    "citation_problem",
    "unclear_answer",
    "not_relevant",
    "other",
]


class FeedbackUpsertRequest(BaseModel):
    """Create or update feedback for one response version."""

    client_id: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )
    rating: FeedbackRating
    reason: FeedbackReason | None = None
    comment: str | None = Field(
        default=None,
        max_length=1000,
    )

    @model_validator(mode="after")
    def validate_feedback(self) -> "FeedbackUpsertRequest":
        """Require a reason for negative feedback and normalize comments."""
        if self.rating == "down" and self.reason is None:
            raise ValueError(
                "A reason is required for thumbs-down feedback."
            )

        if self.rating == "up":
            self.reason = None
            self.comment = None
        elif self.comment is not None:
            cleaned_comment = self.comment.strip()
            self.comment = cleaned_comment or None

        return self


class FeedbackResponse(BaseModel):
    """One saved rating for one exact response version."""

    id: str
    client_id: str
    conversation_id: str
    message_id: str
    version_id: str
    version_number: int
    rating: FeedbackRating
    reason: FeedbackReason | None
    comment: str | None
    created_at: str
    updated_at: str


class FeedbackLookupResponse(BaseModel):
    """Existing feedback for one version, or null when unrated."""

    feedback: FeedbackResponse | None
