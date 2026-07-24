export type MessageRole =
  | "user"
  | "assistant"

export type MessageStatus =
  | "complete"
  | "streaming"
  | "stopped"
  | "error"

export interface ChatSource {
  sourceId: number
  chunkId: string
  sourceDocument: string
  sectionTitle: string
  pageNumber: number | null
  endPageNumber: number | null
  snippet?: string | null
}


export type FeedbackRating =
  | "up"
  | "down"

export type FeedbackReason =
  | "incorrect_answer"
  | "missing_information"
  | "citation_problem"
  | "unclear_answer"
  | "not_relevant"
  | "other"

export interface MessageFeedback {
  id: string
  clientId: string
  conversationId: string
  messageId: string
  versionId: string
  versionNumber: number
  rating: FeedbackRating
  reason: FeedbackReason | null
  comment: string | null
  createdAt: string
  updatedAt: string
}

export interface ApiFeedback {
  id: string
  client_id: string
  conversation_id: string
  message_id: string
  version_id: string
  version_number: number
  rating: FeedbackRating
  reason: FeedbackReason | null
  comment: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  createdAt: string
  updatedAt?: string
  status: MessageStatus
  refused?: boolean
  sources?: ChatSource[]
  activeVersionId?: string | null
  activeVersionNumber?: number | null
  versionCount?: number
  feedback?: MessageFeedback | null
}

export interface ChatConversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messageCount: number
  lastMessagePreview: string
  messages: ChatMessage[]
}

export interface ApiSource {
  source_id: number
  chunk_id: string
  source_document: string
  section_title: string
  page_number: number | null
  end_page_number: number | null
  snippet?: string | null
}

export interface ApiMessage {
  id: string
  role: MessageRole
  content: string
  status: MessageStatus
  refused: boolean
  sources: ApiSource[]
  active_version_id: string | null
  active_version_number: number | null
  version_count: number
  created_at: string
  updated_at: string
}

export interface ApiConversationSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  last_message_preview: string
}

export interface ApiConversationDetail
  extends ApiConversationSummary {
  messages: ApiMessage[]
}

export interface ApiResponseVersion {
  id: string
  message_id: string
  version_number: number
  content: string
  status: MessageStatus
  refused: boolean
  sources: ApiSource[]
  created_at: string
}

export interface ResponseVersion {
  id: string
  messageId: string
  versionNumber: number
  content: string
  status: MessageStatus
  refused: boolean
  sources: ChatSource[]
  createdAt: string
}

export interface ResponseVersionHistory {
  messageId: string
  activeVersionId: string | null
  activeVersionNumber: number | null
  versionCount: number
  versions: ResponseVersion[]
}

export interface AskRequest {
  question: string
  client_id?: string
  conversation_id?: string | null
}

export interface AskResponse {
  answer: string
  refused: boolean
  sources: ApiSource[]
}

export interface HealthResponse {
  status: string
  api: boolean
  weaviate: boolean
  mongodb: boolean
  ollama: boolean
  models_loaded: boolean
}

export type BackendStatus =
  | "checking"
  | "online"
  | "offline"
