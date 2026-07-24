import type {
  ApiConversationDetail,
  ApiConversationSummary,
  ApiFeedback,
  ApiMessage,
  ApiSource,
  ApiResponseVersion,
  AskRequest,
  AskResponse,
  ChatConversation,
  ChatMessage,
  ChatSource,
  FeedbackRating,
  FeedbackReason,
  HealthResponse,
  MessageFeedback,
  ResponseVersion,
  ResponseVersionHistory,
} from "@/types/chat"

export const RAG_API_BASE_URL =
  import.meta.env.VITE_RAG_API_URL ??
  "http://127.0.0.1:8000"

interface ConversationListResponse {
  conversations:
    ApiConversationSummary[]
}

interface DeleteConversationResponse {
  deleted: boolean
  conversation_id: string
}

interface FeedbackLookupResponse {
  feedback: ApiFeedback | null
}

interface StreamStatusPayload {
  stage: string
  message: string
}

interface StreamConversationPayload {
  conversation:
    ApiConversationSummary
  user_message: ApiMessage
  assistant_message: ApiMessage
}

interface StreamRegenerationPayload {
  assistant_message: ApiMessage
}

interface ApiResponseVersionHistory {
  message_id: string
  active_version_id: string | null
  active_version_number: number | null
  version_count: number
  versions: ApiResponseVersion[]
}

interface StreamSourcesPayload {
  sources: ApiSource[]
}

export interface StreamDonePayload {
  refused: boolean
  conversation_id?: string
  assistant_message_id?: string
  version_id?: string | null
  version_number?: number | null
  version_count?: number | null
}

interface StreamErrorPayload {
  message: string
}

export interface ConversationStartedPayload {
  conversation: ChatConversation
  userMessage: ChatMessage
  assistantMessage: ChatMessage
}

export interface StreamCallbacks {
  onConversation?: (
    payload:
      ConversationStartedPayload,
  ) => void
  onRegeneration?: (
    assistantMessage: ChatMessage,
  ) => void
  onStatus: (
    payload: StreamStatusPayload,
  ) => void
  onToken: (text: string) => void
  onSources: (
    sources: ChatSource[],
  ) => void
  onDone: (
    payload: StreamDonePayload,
  ) => void
}

async function parseJsonResponse<T>(
  response: Response,
): Promise<T> {
  if (!response.ok) {
    let details =
      `Request failed with status ${response.status}`

    try {
      const payload =
        (await response.json()) as {
          detail?:
            | string
            | Array<{ msg?: string }>
        }

      if (
        typeof payload.detail
        === "string"
      ) {
        details = payload.detail
      } else if (
        Array.isArray(
          payload.detail,
        )
      ) {
        details = payload.detail
          .map((item) => item.msg)
          .filter(Boolean)
          .join(", ")
      }
    } catch {
      // Keep the HTTP fallback when
      // the response is not JSON.
    }

    throw new Error(details)
  }

  return (
    await response.json()
  ) as T
}

function mapSource(
  source: ApiSource,
): ChatSource {
  return {
    sourceId: source.source_id,
    chunkId: source.chunk_id,
    sourceDocument:
      source.source_document,
    sectionTitle:
      source.section_title,
    pageNumber:
      source.page_number,
    endPageNumber:
      source.end_page_number,
    snippet:
      source.snippet ?? null,
  }
}

function mapSources(
  sources: ApiSource[],
): ChatSource[] {
  return sources.map(
    mapSource,
  )
}

function mapFeedback(
  feedback: ApiFeedback,
): MessageFeedback {
  return {
    id: feedback.id,
    clientId: feedback.client_id,
    conversationId:
      feedback.conversation_id,
    messageId: feedback.message_id,
    versionId: feedback.version_id,
    versionNumber:
      feedback.version_number,
    rating: feedback.rating,
    reason: feedback.reason,
    comment: feedback.comment,
    createdAt: feedback.created_at,
    updatedAt: feedback.updated_at,
  }
}

function mapMessage(
  message: ApiMessage,
): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    status: message.status,
    refused: message.refused,
    sources: mapSources(
      message.sources,
    ),
    activeVersionId:
      message.active_version_id,
    activeVersionNumber:
      message.active_version_number,
    versionCount:
      message.version_count,
    createdAt:
      message.created_at,
    updatedAt:
      message.updated_at,
    feedback: null,
  }
}

function mapResponseVersion(
  version: ApiResponseVersion,
): ResponseVersion {
  return {
    id: version.id,
    messageId: version.message_id,
    versionNumber:
      version.version_number,
    content: version.content,
    status: version.status,
    refused: version.refused,
    sources: mapSources(
      version.sources,
    ),
    createdAt: version.created_at,
  }
}

function mapConversationSummary(
  conversation:
    ApiConversationSummary,
  messages: ChatMessage[] = [],
): ChatConversation {
  return {
    id: conversation.id,
    title: conversation.title,
    createdAt:
      conversation.created_at,
    updatedAt:
      conversation.updated_at,
    messageCount:
      conversation.message_count,
    lastMessagePreview:
      conversation.last_message_preview,
    messages,
  }
}

function mapConversationDetail(
  conversation:
    ApiConversationDetail,
): ChatConversation {
  return mapConversationSummary(
    conversation,
    conversation.messages.map(
      mapMessage,
    ),
  )
}

export async function getHealth(
  signal?: AbortSignal,
): Promise<HealthResponse> {
  const response = await fetch(
    `${RAG_API_BASE_URL}/health`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  )

  return parseJsonResponse<
    HealthResponse
  >(response)
}

export async function listConversations(
  clientId: string,
  signal?: AbortSignal,
): Promise<ChatConversation[]> {
  const query =
    new URLSearchParams({
      client_id: clientId,
      limit: "100",
    })

  const response = await fetch(
    `${RAG_API_BASE_URL}/conversations?${query}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  )

  const payload =
    await parseJsonResponse<
      ConversationListResponse
    >(response)

  return payload.conversations.map(
    (conversation) =>
      mapConversationSummary(
        conversation,
      ),
  )
}

export async function getConversation(
  clientId: string,
  conversationId: string,
  signal?: AbortSignal,
): Promise<ChatConversation> {
  const query =
    new URLSearchParams({
      client_id: clientId,
    })

  const response = await fetch(
    `${RAG_API_BASE_URL}/conversations/${conversationId}?${query}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  )

  const payload =
    await parseJsonResponse<
      ApiConversationDetail
    >(response)

  const conversation =
    mapConversationDetail(
      payload,
    )

  const messages =
    await Promise.all(
      conversation.messages.map(
        async (message) => {
          if (
            message.role !== "assistant"
            || !message.activeVersionNumber
          ) {
            return message
          }

          try {
            const feedback =
              await getResponseFeedback(
                clientId,
                message.id,
                message.activeVersionNumber,
                signal,
              )

            return {
              ...message,
              feedback,
            }
          } catch {
            return {
              ...message,
              feedback: null,
            }
          }
        },
      ),
    )

  return {
    ...conversation,
    messages,
  }
}

export async function deleteConversation(
  clientId: string,
  conversationId: string,
): Promise<void> {
  const query =
    new URLSearchParams({
      client_id: clientId,
    })

  const response = await fetch(
    `${RAG_API_BASE_URL}/conversations/${conversationId}?${query}`,
    {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    },
  )

  const payload =
    await parseJsonResponse<
      DeleteConversationResponse
    >(response)

  if (!payload.deleted) {
    throw new Error(
      "The conversation was not deleted.",
    )
  }
}

export async function askQuestion(
  question: string,
): Promise<{
  answer: string
  refused: boolean
  sources: ChatSource[]
}> {
  const requestBody: AskRequest = {
    question,
  }

  const response = await fetch(
    `${RAG_API_BASE_URL}/ask`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(
        requestBody,
      ),
    },
  )

  const payload =
    await parseJsonResponse<
      AskResponse
    >(response)

  return {
    answer: payload.answer,
    refused: payload.refused,
    sources: mapSources(
      payload.sources,
    ),
  }
}

export async function listResponseVersions(
  clientId: string,
  assistantMessageId: string,
): Promise<ResponseVersionHistory> {
  const query =
    new URLSearchParams({
      client_id: clientId,
    })

  const response = await fetch(
    `${RAG_API_BASE_URL}/messages/${assistantMessageId}/versions?${query}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    },
  )

  const payload =
    await parseJsonResponse<
      ApiResponseVersionHistory
    >(response)

  return {
    messageId: payload.message_id,
    activeVersionId:
      payload.active_version_id,
    activeVersionNumber:
      payload.active_version_number,
    versionCount:
      payload.version_count,
    versions: payload.versions.map(
      mapResponseVersion,
    ),
  }
}

export async function activateResponseVersion(
  clientId: string,
  assistantMessageId: string,
  versionNumber: number,
): Promise<ChatMessage> {
  const query =
    new URLSearchParams({
      client_id: clientId,
    })

  const response = await fetch(
    `${RAG_API_BASE_URL}/messages/${assistantMessageId}/versions/${versionNumber}/activate?${query}`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    },
  )

  const payload =
    await parseJsonResponse<
      ApiMessage
    >(response)

  const message =
    mapMessage(payload)

  const feedback =
    await getResponseFeedback(
      clientId,
      assistantMessageId,
      versionNumber,
    )

  return {
    ...message,
    feedback,
  }
}

export async function getResponseFeedback(
  clientId: string,
  assistantMessageId: string,
  versionNumber: number,
  signal?: AbortSignal,
): Promise<MessageFeedback | null> {
  const query =
    new URLSearchParams({
      client_id: clientId,
    })

  const response = await fetch(
    `${RAG_API_BASE_URL}/messages/${assistantMessageId}/versions/${versionNumber}/feedback?${query}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  )

  const payload =
    await parseJsonResponse<
      FeedbackLookupResponse
    >(response)

  return payload.feedback
    ? mapFeedback(payload.feedback)
    : null
}

export async function saveResponseFeedback(
  clientId: string,
  assistantMessageId: string,
  versionNumber: number,
  rating: FeedbackRating,
  reason: FeedbackReason | null = null,
  comment: string | null = null,
): Promise<MessageFeedback> {
  const response = await fetch(
    `${RAG_API_BASE_URL}/messages/${assistantMessageId}/versions/${versionNumber}/feedback`,
    {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        client_id: clientId,
        rating,
        reason,
        comment,
      }),
    },
  )

  const payload =
    await parseJsonResponse<
      ApiFeedback
    >(response)

  return mapFeedback(payload)
}

function processSseBlock(
  block: string,
  callbacks: StreamCallbacks,
): boolean {
  let eventName = "message"
  const dataLines: string[] = []

  for (
    const line
    of block.split(/\r?\n/)
  ) {
    if (
      line.startsWith("event:")
    ) {
      eventName = line
        .slice("event:".length)
        .trim()
    }

    if (
      line.startsWith("data:")
    ) {
      dataLines.push(
        line
          .slice("data:".length)
          .trimStart(),
      )
    }
  }

  if (
    dataLines.length === 0
  ) {
    return false
  }

  const payload = JSON.parse(
    dataLines.join("\n"),
  ) as unknown

  switch (eventName) {
    case "conversation": {
      const conversationPayload =
        payload as
          StreamConversationPayload

      callbacks.onConversation?.({
        conversation:
          mapConversationSummary(
            conversationPayload
              .conversation,
          ),
        userMessage:
          mapMessage(
            conversationPayload
              .user_message,
          ),
        assistantMessage:
          mapMessage(
            conversationPayload
              .assistant_message,
          ),
      })

      return false
    }

    case "regeneration": {
      const regenerationPayload =
        payload as
          StreamRegenerationPayload

      callbacks.onRegeneration?.(
        mapMessage(
          regenerationPayload
            .assistant_message,
        ),
      )

      return false
    }

    case "status":
      callbacks.onStatus(
        payload as StreamStatusPayload,
      )
      return false

    case "token":
      callbacks.onToken(
        (payload as { text: string })
          .text,
      )
      return false

    case "sources":
      callbacks.onSources(
        mapSources(
          (
            payload as
              StreamSourcesPayload
          ).sources,
        ),
      )
      return false

    case "done":
      callbacks.onDone(
        payload as StreamDonePayload,
      )
      return true

    case "error":
      throw new Error(
        (
          payload as
            StreamErrorPayload
        ).message,
      )

    default:
      return false
  }
}

export async function streamQuestion(
  question: string,
  clientId: string,
  conversationId: string | null,
  callbacks: StreamCallbacks,
  signal: AbortSignal,
): Promise<void> {
  const requestBody: AskRequest = {
    question,
    client_id: clientId,
    conversation_id:
      conversationId,
  }

  const response = await fetch(
    `${RAG_API_BASE_URL}/ask/stream`,
    {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(
        requestBody,
      ),
      signal,
    },
  )

  if (!response.ok) {
    await parseJsonResponse(
      response,
    )
  }

  if (!response.body) {
    throw new Error(
      "The browser did not receive "
      + "a streaming response body.",
    )
  }

  const reader =
    response.body.getReader()
  const decoder =
    new TextDecoder()

  let buffer = ""
  let completed = false

  try {
    while (!completed) {
      const {
        done,
        value,
      } = await reader.read()

      if (done) {
        buffer += decoder.decode()
        break
      }

      buffer += decoder.decode(
        value,
        {
          stream: true,
        },
      )

      let boundary =
        buffer.indexOf("\n\n")

      while (boundary >= 0) {
        const block = buffer.slice(
          0,
          boundary,
        )

        buffer = buffer.slice(
          boundary + 2,
        )

        if (block.trim()) {
          completed =
            processSseBlock(
              block,
              callbacks,
            )
        }

        if (completed) {
          break
        }

        boundary =
          buffer.indexOf("\n\n")
      }
    }

    if (
      !completed
      && buffer.trim()
    ) {
      completed =
        processSseBlock(
          buffer,
          callbacks,
        )
    }

    if (!completed) {
      throw new Error(
        "The streaming response "
        + "ended unexpectedly.",
      )
    }
  } finally {
    reader.releaseLock()
  }
}


export async function streamRegeneration(
  clientId: string,
  conversationId: string,
  assistantMessageId: string,
  callbacks: StreamCallbacks,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `${RAG_API_BASE_URL}/messages/${assistantMessageId}/regenerate/stream`,
    {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        client_id: clientId,
        conversation_id:
          conversationId,
      }),
      signal,
    },
  )

  if (!response.ok) {
    await parseJsonResponse(response)
  }

  if (!response.body) {
    throw new Error(
      "The browser did not receive "
      + "a streaming response body.",
    )
  }

  const reader =
    response.body.getReader()
  const decoder =
    new TextDecoder()
  let buffer = ""
  let completed = false

  try {
    while (!completed) {
      const {
        done,
        value,
      } = await reader.read()

      if (done) {
        buffer += decoder.decode()
        break
      }

      buffer += decoder.decode(
        value,
        { stream: true },
      )

      let boundary =
        buffer.indexOf("\n\n")

      while (boundary >= 0) {
        const block = buffer.slice(
          0,
          boundary,
        )
        buffer = buffer.slice(
          boundary + 2,
        )

        if (block.trim()) {
          completed = processSseBlock(
            block,
            callbacks,
          )
        }

        if (completed) {
          break
        }

        boundary =
          buffer.indexOf("\n\n")
      }
    }

    if (
      !completed
      && buffer.trim()
    ) {
      completed = processSseBlock(
        buffer,
        callbacks,
      )
    }

    if (!completed) {
      throw new Error(
        "The streaming response "
        + "ended unexpectedly.",
      )
    }
  } finally {
    reader.releaseLock()
  }
}
