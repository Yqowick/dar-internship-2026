import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"

import {
  AppHeader,
} from "@/components/chat/AppHeader"
import {
  FeedbackModal,
} from "@/components/chat/FeedbackModal"
import {
  GuidedTour,
} from "@/components/chat/GuidedTour"
import {
  ChatInput,
} from "@/components/chat/ChatInput"
import {
  ChatSidebar,
} from "@/components/chat/ChatSidebar"
import {
  ChatViewport,
} from "@/components/chat/ChatViewport"
import {
  WelcomeScreen,
} from "@/components/chat/WelcomeScreen"
import {
  createConversationTitle,
  sortConversations,
} from "@/services/chatStorage"
import {
  getOrCreateClientId,
} from "@/services/clientId"
import {
  hasCompletedGuidedTour,
  markGuidedTourCompleted,
} from "@/services/guidedTourStorage"
import {
  activateResponseVersion,
  deleteConversation as
    deleteConversationFromApi,
  getConversation,
  getHealth,
  listConversations,
  saveResponseFeedback,
  streamQuestion,
  streamRegeneration,
} from "@/services/ragApi"
import type {
  BackendStatus,
  ChatConversation,
  ChatMessage,
  ChatSource,
  FeedbackReason,
  HealthResponse,
  MessageFeedback,
} from "@/types/chat"

function createTemporaryId(
  prefix: string,
): string {
  return (
    `${prefix}-${Date.now()}-`
    + crypto.randomUUID()
  )
}

function isAbortError(
  error: unknown,
): boolean {
  return (
    error instanceof Error
    && error.name === "AbortError"
  )
}

function statusFromHealth(
  health: HealthResponse,
): BackendStatus {
  const isHealthy =
    health.status === "healthy"
    && health.api
    && health.weaviate
    && health.mongodb
    && health.ollama
    && health.models_loaded

  return isHealthy
    ? "online"
    : "offline"
}

const clientId =
  getOrCreateClientId()

export default function App() {
  const [
    conversations,
    setConversations,
  ] = useState<
    ChatConversation[]
  >([])

  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState<
    string | null
  >(null)

  const [
    isNewChatOpen,
    setIsNewChatOpen,
  ] = useState(false)

  const [
    sidebarOpen,
    setSidebarOpen,
  ] = useState(
    () =>
      window.matchMedia(
        "(min-width: 1024px)",
      ).matches,
  )

  const [
    backendStatus,
    setBackendStatus,
  ] = useState<
    BackendStatus
  >("checking")

  const [
    isLoading,
    setIsLoading,
  ] = useState(false)

  const [
    activeOperationMessageId,
    setActiveOperationMessageId,
  ] = useState<
    string | null
  >(null)

  const [
    activeOperationKind,
    setActiveOperationKind,
  ] = useState<
    "regenerate"
    | "switch"
    | "feedback"
    | null
  >(null)

  const [
    guidedTourOpen,
    setGuidedTourOpen,
  ] = useState(false)

  const [
    feedbackModal,
    setFeedbackModal,
  ] = useState<{
    messageId: string
    versionNumber: number
    existingFeedback:
      MessageFeedback | null
  } | null>(null)

  const [
    isLoadingHistory,
    setIsLoadingHistory,
  ] = useState(true)

  const [
    historyError,
    setHistoryError,
  ] = useState<
    string | null
  >(null)

  const [
    thinkingLabel,
    setThinkingLabel,
  ] = useState(
    "Searching the CIS document…",
  )

  const abortControllerRef =
    useRef<
      AbortController | null
    >(null)

  const activeConversation =
    useMemo(
      () =>
        conversations.find(
          (conversation) =>
            conversation.id
            === activeConversationId,
        ) ?? null,
      [
        conversations,
        activeConversationId,
      ],
    )

  const mergeConversation = (
    conversation:
      ChatConversation,
  ) => {
    setConversations(
      (currentConversations) =>
        sortConversations([
          conversation,
          ...currentConversations.filter(
            (item) =>
              item.id
              !== conversation.id,
          ),
        ]),
    )
  }

  const refreshConversationList =
    async () => {
      setIsLoadingHistory(true)
      setHistoryError(null)

      try {
        const serverConversations =
          await listConversations(
            clientId,
          )

        setConversations(
          (currentConversations) =>
            sortConversations(
              serverConversations.map(
                (conversation) => {
                  const existing =
                    currentConversations
                      .find(
                        (item) =>
                          item.id
                          === conversation.id,
                      )

                  return {
                    ...conversation,
                    messages:
                      existing
                        ?.messages
                        ?? [],
                  }
                },
              ),
            ),
        )
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : (
              "Unable to load "
              + "chat history."
            )

        setHistoryError(message)
      } finally {
        setIsLoadingHistory(
          false,
        )
      }
    }

  const refreshBackendStatus =
    () => {
      getHealth()
        .then((health) => {
          setBackendStatus(
            statusFromHealth(
              health,
            ),
          )
        })
        .catch(() => {
          setBackendStatus(
            "offline",
          )
        })
    }

  const synchronizeConversation =
    async (
      conversationId: string,
    ) => {
      try {
        const conversation =
          await getConversation(
            clientId,
            conversationId,
          )

        mergeConversation(
          conversation,
        )
      } catch {
        // The sidebar refresh will surface
        // a persistent backend issue.
      }
    }

  useEffect(() => {
    if (
      isLoadingHistory
      || hasCompletedGuidedTour()
    ) {
      return
    }

    const timer =
      window.setTimeout(
        () => {
          setSidebarOpen(true)
          setGuidedTourOpen(true)
        },
        700,
      )

    return () => {
      window.clearTimeout(timer)
    }
  }, [isLoadingHistory])

  useEffect(() => {
    document.title =
      "CIS Controls Assistant"

    const controller =
      new AbortController()

    Promise.allSettled([
      getHealth(
        controller.signal,
      ).then((health) => {
        setBackendStatus(
          statusFromHealth(
            health,
          ),
        )
      }),
      listConversations(
        clientId,
        controller.signal,
      ).then((serverConversations) => {
        setConversations(
          sortConversations(
            serverConversations,
          ),
        )
        setHistoryError(null)
      }),
    ]).then((results) => {
      if (
        results[0].status
        === "rejected"
      ) {
        setBackendStatus(
          "offline",
        )
      }

      if (
        results[1].status
        === "rejected"
      ) {
        const reason =
          results[1].reason

        setHistoryError(
          reason instanceof Error
            ? reason.message
            : (
              "Unable to load "
              + "chat history."
            ),
        )
      }

      setIsLoadingHistory(
        false,
      )
    })

    return () => {
      controller.abort()

      abortControllerRef
        .current
        ?.abort()
    }
  }, [])

  const stopActiveRequest =
    () => {
      abortControllerRef
        .current
        ?.abort()
  }

  const closeSidebarOnSmallScreens =
    () => {
      const isDesktop =
        window.matchMedia(
          "(min-width: 1024px)",
        ).matches

      if (!isDesktop) {
        setSidebarOpen(false)
      }
    }

  const beginNewChat =
    () => {
      stopActiveRequest()
      setActiveConversationId(
        null,
      )
      setIsNewChatOpen(true)
      closeSidebarOnSmallScreens()
    }

  const selectConversation =
    async (
      conversationId: string,
    ) => {
      stopActiveRequest()
      closeSidebarOnSmallScreens()
      setIsNewChatOpen(false)
      setActiveConversationId(
        conversationId,
      )

      try {
        const conversation =
          await getConversation(
            clientId,
            conversationId,
          )

        mergeConversation(
          conversation,
        )
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : (
              "Unable to open "
              + "this conversation."
            )

        setHistoryError(message)
      }
    }

  const deleteConversation =
    async (
      conversationId: string,
    ) => {
      const conversation =
        conversations.find(
          (item) =>
            item.id
            === conversationId,
        )

      if (!conversation) {
        return
      }

      const shouldDelete =
        window.confirm(
          `Delete "${conversation.title}"?`,
        )

      if (!shouldDelete) {
        return
      }

      try {
        await deleteConversationFromApi(
          clientId,
          conversationId,
        )

        if (
          activeConversationId
          === conversationId
        ) {
          stopActiveRequest()
          setActiveConversationId(
            null,
          )
          setIsNewChatOpen(
            false,
          )
        }

        setConversations(
          (currentConversations) =>
            currentConversations.filter(
              (item) =>
                item.id
                !== conversationId,
            ),
        )
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : (
              "Unable to delete "
              + "the conversation."
            )

        setHistoryError(message)
      }
    }

  const updateAssistantMessage = (
    conversationId: string,
    messageId: string,
    update: (
      message: ChatMessage,
    ) => ChatMessage,
  ) => {
    setConversations(
      (currentConversations) =>
        sortConversations(
          currentConversations.map(
            (conversation) =>
              conversation.id
                === conversationId
                ? {
                    ...conversation,
                    updatedAt:
                      new Date()
                        .toISOString(),
                    messages:
                      conversation
                        .messages
                        .map(
                          (message) =>
                            message.id
                              === messageId
                              ? update(
                                  message,
                                )
                              : message,
                        ),
                  }
                : conversation,
          ),
        ),
    )
  }

  const handleRegenerate = async (
    assistantMessageId: string,
  ) => {
    if (
      isLoading
      || activeOperationKind !== null
      || !activeConversation
    ) {
      return
    }

    const originalMessage =
      activeConversation.messages.find(
        (message) =>
          message.id
          === assistantMessageId,
      )

    if (
      !originalMessage
      || originalMessage.role
        !== "assistant"
    ) {
      return
    }

    setIsLoading(true)
    setActiveOperationMessageId(
      assistantMessageId,
    )
    setActiveOperationKind(
      "regenerate",
    )
    setThinkingLabel(
      "Regenerating the answer…",
    )

    updateAssistantMessage(
      activeConversation.id,
      assistantMessageId,
      (message) => ({
        ...message,
        status: "streaming",
      }),
    )

    const controller =
      new AbortController()

    abortControllerRef.current =
      controller

    let receivedFirstToken = false

    try {
      await streamRegeneration(
        clientId,
        activeConversation.id,
        assistantMessageId,
        {
          onRegeneration: () => {
            // The existing answer remains visible
            // until the first new token arrives.
          },
          onStatus: (status) => {
            setThinkingLabel(
              status.message,
            )
          },
          onToken: (text) => {
            updateAssistantMessage(
              activeConversation.id,
              assistantMessageId,
              (message) => ({
                ...message,
                content:
                  receivedFirstToken
                    ? message.content
                      + text
                    : text,
                sources:
                  receivedFirstToken
                    ? message.sources
                    : [],
                status: "streaming",
              }),
            )

            receivedFirstToken = true
          },
          onSources: (
            sources: ChatSource[],
          ) => {
            updateAssistantMessage(
              activeConversation.id,
              assistantMessageId,
              (message) => ({
                ...message,
                sources,
              }),
            )
          },
          onDone: (payload) => {
            updateAssistantMessage(
              activeConversation.id,
              assistantMessageId,
              (message) => ({
                ...message,
                status: "complete",
                refused:
                  payload.refused,
                activeVersionId:
                  payload.version_id
                  ?? message.activeVersionId
                  ?? null,
                activeVersionNumber:
                  payload.version_number
                  ?? message.activeVersionNumber
                  ?? null,
                versionCount:
                  payload.version_count
                  ?? payload.version_number
                  ?? message.versionCount
                  ?? 1,
                feedback: null,
              }),
            )
          },
        },
        controller.signal,
      )

      setBackendStatus(
        "online",
      )

      await synchronizeConversation(
        activeConversation.id,
      )
    } catch (error) {
      if (isAbortError(error)) {
        updateAssistantMessage(
          activeConversation.id,
          assistantMessageId,
          (message) => ({
            ...message,
            status:
              receivedFirstToken
                ? "stopped"
                : originalMessage.status,
            content:
              receivedFirstToken
                ? message.content
                : originalMessage.content,
            sources:
              receivedFirstToken
                ? message.sources
                : originalMessage.sources,
          }),
        )
      } else {
        updateAssistantMessage(
          activeConversation.id,
          assistantMessageId,
          () => originalMessage,
        )
        refreshBackendStatus()
      }

      window.setTimeout(
        () => {
          void synchronizeConversation(
            activeConversation.id,
          )
        },
        700,
      )
    } finally {
      abortControllerRef.current =
        null
      setIsLoading(false)
      setActiveOperationMessageId(
        null,
      )
      setActiveOperationKind(
        null,
      )
      setThinkingLabel(
        "Searching the CIS document…",
      )
    }
  }

  const handleSwitchVersion = async (
    assistantMessageId: string,
    versionNumber: number,
  ) => {
    if (
      isLoading
      || activeOperationKind !== null
      || !activeConversation
    ) {
      return
    }

    setActiveOperationMessageId(
      assistantMessageId,
    )
    setActiveOperationKind(
      "switch",
    )

    try {
      const updatedMessage =
        await activateResponseVersion(
          clientId,
          assistantMessageId,
          versionNumber,
        )

      updateAssistantMessage(
        activeConversation.id,
        assistantMessageId,
        () => updatedMessage,
      )
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : (
            "Unable to switch "
            + "response versions."
          )

      setHistoryError(message)
    } finally {
      setActiveOperationMessageId(
        null,
      )
      setActiveOperationKind(
        null,
      )
    }
  }

  const activeAssistantMessage = (
    assistantMessageId: string,
  ) => {
    if (!activeConversation) {
      return null
    }

    return (
      activeConversation.messages.find(
        (message) =>
          message.id
          === assistantMessageId
          && message.role
          === "assistant",
      ) ?? null
    )
  }

  const handleThumbsUp = async (
    assistantMessageId: string,
  ) => {
    if (
      isLoading
      || activeOperationKind !== null
      || !activeConversation
    ) {
      return
    }

    const message =
      activeAssistantMessage(
        assistantMessageId,
      )
    const versionNumber =
      message?.activeVersionNumber

    if (
      !message
      || !versionNumber
      || message.feedback?.rating
        === "up"
    ) {
      return
    }

    setActiveOperationMessageId(
      assistantMessageId,
    )
    setActiveOperationKind(
      "feedback",
    )

    try {
      const feedback =
        await saveResponseFeedback(
          clientId,
          assistantMessageId,
          versionNumber,
          "up",
        )

      updateAssistantMessage(
        activeConversation.id,
        assistantMessageId,
        (currentMessage) => ({
          ...currentMessage,
          feedback,
        }),
      )
    } catch (error) {
      const messageText =
        error instanceof Error
          ? error.message
          : "Unable to save feedback."

      setHistoryError(messageText)
    } finally {
      setActiveOperationMessageId(
        null,
      )
      setActiveOperationKind(
        null,
      )
    }
  }

  const handleThumbsDown = (
    assistantMessageId: string,
  ) => {
    if (
      isLoading
      || activeOperationKind !== null
    ) {
      return
    }

    const message =
      activeAssistantMessage(
        assistantMessageId,
      )
    const versionNumber =
      message?.activeVersionNumber

    if (!message || !versionNumber) {
      return
    }

    setFeedbackModal({
      messageId: assistantMessageId,
      versionNumber,
      existingFeedback:
        message.feedback ?? null,
    })
  }

  const submitNegativeFeedback =
    async (
      reason: FeedbackReason,
      comment: string | null,
    ) => {
      if (
        !feedbackModal
        || !activeConversation
        || activeOperationKind !== null
      ) {
        return
      }

      setActiveOperationMessageId(
        feedbackModal.messageId,
      )
      setActiveOperationKind(
        "feedback",
      )

      try {
        const feedback =
          await saveResponseFeedback(
            clientId,
            feedbackModal.messageId,
            feedbackModal.versionNumber,
            "down",
            reason,
            comment,
          )

        updateAssistantMessage(
          activeConversation.id,
          feedbackModal.messageId,
          (message) => ({
            ...message,
            feedback,
          }),
        )

        setFeedbackModal(null)
      } catch (error) {
        const messageText =
          error instanceof Error
            ? error.message
            : "Unable to save feedback."

        setHistoryError(messageText)
      } finally {
        setActiveOperationMessageId(
          null,
        )
        setActiveOperationKind(
          null,
        )
      }
    }

  const handleSend = async (
    question: string,
  ) => {
    if (
      isLoading
      || activeOperationKind !== null
    ) {
      return
    }

    const now =
      new Date().toISOString()

    const temporaryUserId =
      createTemporaryId("user")

    const temporaryAssistantId =
      createTemporaryId(
        "assistant",
      )

    const temporaryConversationId =
      activeConversationId
      ?? createTemporaryId(
        "conversation",
      )

    const existingConversationId =
      activeConversationId

    const userMessage:
      ChatMessage = {
        id: temporaryUserId,
        role: "user",
        content: question,
        createdAt: now,
        updatedAt: now,
        status: "complete",
        refused: false,
        sources: [],
        activeVersionId: null,
        activeVersionNumber: null,
        versionCount: 0,
      }

    const assistantMessage:
      ChatMessage = {
        id: temporaryAssistantId,
        role: "assistant",
        content: "",
        createdAt: now,
        updatedAt: now,
        status: "streaming",
        refused: false,
        sources: [],
        activeVersionId: null,
        activeVersionNumber: null,
        versionCount: 0,
      }

    if (existingConversationId) {
      setConversations(
        (currentConversations) =>
          sortConversations(
            currentConversations.map(
              (conversation) =>
                conversation.id
                  === existingConversationId
                  ? {
                      ...conversation,
                      updatedAt: now,
                      messageCount:
                        conversation
                          .messageCount
                        + 2,
                      lastMessagePreview:
                        question,
                      messages: [
                        ...conversation
                          .messages,
                        userMessage,
                        assistantMessage,
                      ],
                    }
                  : conversation,
            ),
          ),
      )
    } else {
      const temporaryConversation:
        ChatConversation = {
          id:
            temporaryConversationId,
          title:
            createConversationTitle(
              question,
            ),
          createdAt: now,
          updatedAt: now,
          messageCount: 2,
          lastMessagePreview:
            question,
          messages: [
            userMessage,
            assistantMessage,
          ],
        }

      setConversations(
        (currentConversations) =>
          sortConversations([
            temporaryConversation,
            ...currentConversations,
          ]),
      )

      setActiveConversationId(
        temporaryConversationId,
      )
      setIsNewChatOpen(false)
    }

    setIsLoading(true)
    setThinkingLabel(
      "Saving your question…",
    )

    const controller =
      new AbortController()

    abortControllerRef.current =
      controller

    const conversationIdRef = {
      current:
        temporaryConversationId,
    }

    const assistantMessageIdRef = {
      current:
        temporaryAssistantId,
    }

    try {
      await streamQuestion(
        question,
        clientId,
        existingConversationId,
        {
          onConversation: (
            payload,
          ) => {
            const oldConversationId =
              conversationIdRef.current

            conversationIdRef.current =
              payload.conversation.id

            assistantMessageIdRef.current =
              payload.assistantMessage.id

            setActiveConversationId(
              payload.conversation.id,
            )

            setConversations(
              (currentConversations) => {
                const existing =
                  currentConversations
                    .find(
                      (conversation) =>
                        conversation.id
                        === oldConversationId,
                    )

                const existingMessages =
                  existing?.messages
                  ?? []

                const messages =
                  existingMessages.map(
                    (message) => {
                      if (
                        message.id
                        === temporaryUserId
                      ) {
                        return (
                          payload.userMessage
                        )
                      }

                      if (
                        message.id
                        === temporaryAssistantId
                      ) {
                        return {
                          ...payload
                            .assistantMessage,
                          content:
                            message.content,
                          sources:
                            message.sources,
                        }
                      }

                      return message
                    },
                  )

                const persistedConversation:
                  ChatConversation = {
                    ...payload
                      .conversation,
                    messages,
                  }

                return sortConversations([
                  persistedConversation,
                  ...currentConversations
                    .filter(
                      (conversation) =>
                        conversation.id
                        !== oldConversationId
                        && conversation.id
                        !== payload
                          .conversation
                          .id,
                    ),
                ])
              },
            )
          },

          onStatus: (status) => {
            setThinkingLabel(
              status.message,
            )
          },

          onToken: (text) => {
            updateAssistantMessage(
              conversationIdRef.current,
              assistantMessageIdRef
                .current,
              (message) => ({
                ...message,
                content:
                  message.content
                  + text,
                status:
                  "streaming",
              }),
            )
          },

          onSources: (
            sources:
              ChatSource[],
          ) => {
            updateAssistantMessage(
              conversationIdRef.current,
              assistantMessageIdRef
                .current,
              (message) => ({
                ...message,
                sources,
              }),
            )
          },

          onDone: (payload) => {
            updateAssistantMessage(
              conversationIdRef.current,
              assistantMessageIdRef
                .current,
              (message) => ({
                ...message,
                status:
                  "complete",
                refused:
                  payload.refused,
                activeVersionId:
                  payload.version_id
                  ?? message
                    .activeVersionId
                  ?? null,
                activeVersionNumber:
                  payload.version_number
                  ?? message
                    .activeVersionNumber
                  ?? null,
                versionCount:
                  payload.version_count
                  ?? payload.version_number
                  ?? message
                    .versionCount
                  ?? 1,
                feedback: null,
              }),
            )
          },
        },
        controller.signal,
      )

      setBackendStatus(
        "online",
      )

      await synchronizeConversation(
        conversationIdRef.current,
      )

      await refreshConversationList()
    } catch (error) {
      if (isAbortError(error)) {
        updateAssistantMessage(
          conversationIdRef.current,
          assistantMessageIdRef
            .current,
          (message) => ({
            ...message,
            content:
              message.content.trim()
                ? message.content
                : "Response stopped.",
            status: "stopped",
          }),
        )
      } else {
        const errorMessage =
          error instanceof Error
            ? error.message
            : (
              "An unexpected error "
              + "occurred."
            )

        updateAssistantMessage(
          conversationIdRef.current,
          assistantMessageIdRef
            .current,
          (message) => ({
            ...message,
            content:
              `${errorMessage}\n\n`
              + "The saved conversation "
              + "will be synchronized "
              + "from MongoDB.",
            status: "error",
            sources: [],
          }),
        )

        refreshBackendStatus()
      }

      window.setTimeout(
        () => {
          void synchronizeConversation(
            conversationIdRef.current,
          )

          void refreshConversationList()
        },
        700,
      )
    } finally {
      abortControllerRef.current =
        null

      setIsLoading(false)
      setThinkingLabel(
        "Searching the CIS document…",
      )
    }
  }

  const activeMessages =
    activeConversation
      ?.messages
      ?? []

  const lastMessage =
    activeMessages.at(-1)

  const waitingForFirstToken =
    isLoading
    && lastMessage?.role
      === "assistant"
    && lastMessage.content
      .length === 0

  const showWelcome =
    activeConversationId
      === null
    && !isNewChatOpen

  return (
    <>
      <main className="app-background h-dvh min-h-[640px] p-0 lg:p-4">
      <section className="app-shell mx-auto flex h-full w-full max-w-[1540px] overflow-hidden lg:rounded-[1.75rem]">
        <ChatSidebar
          conversations={
            conversations
          }
          activeConversationId={
            activeConversationId
          }
          isOpen={
            sidebarOpen
          }
          isLoadingHistory={
            isLoadingHistory
          }
          historyError={
            historyError
          }
          onClose={() =>
            setSidebarOpen(false)
          }
          onNewChat={
            beginNewChat
          }
          onSelectConversation={(
            conversationId,
          ) => {
            void selectConversation(
              conversationId,
            )
          }}
          onDeleteConversation={(
            conversationId,
          ) => {
            void deleteConversation(
              conversationId,
            )
          }}
        />

        <div className="cyber-grid flex min-w-0 flex-1 flex-col bg-background/65">
          <AppHeader
            backendStatus={
              backendStatus
            }
            conversationTitle={
              activeConversation
                ?.title
                ?? null
            }
            isSidebarOpen={
              sidebarOpen
            }
            onToggleSidebar={() =>
              setSidebarOpen(
                (currentValue) =>
                  !currentValue,
              )
            }
            onReplayTour={() => {
              setSidebarOpen(true)
              setGuidedTourOpen(true)
            }}
          />

          {showWelcome ? (
            <WelcomeScreen
              onStartNewChat={
                beginNewChat
              }
              onAskSuggestion={(
                question,
              ) => {
                void handleSend(
                  question,
                )
              }}
            />
          ) : (
            <>
              <ChatViewport
                messages={
                  activeMessages
                }
                showThinkingIndicator={
                  waitingForFirstToken
                }
                thinkingLabel={
                  thinkingLabel
                }
                busyMessageId={
                  activeOperationMessageId
                }
                busyAction={
                  activeOperationKind
                }
                interactionsDisabled={
                  isLoading
                  || activeOperationKind
                    !== null
                }
                onThumbsUp={(
                  messageId,
                ) => {
                  void handleThumbsUp(
                    messageId,
                  )
                }}
                onThumbsDown={(
                  messageId,
                ) => {
                  handleThumbsDown(
                    messageId,
                  )
                }}
                onRegenerate={(
                  messageId,
                ) => {
                  void handleRegenerate(
                    messageId,
                  )
                }}
                onSwitchVersion={(
                  messageId,
                  versionNumber,
                ) => {
                  void handleSwitchVersion(
                    messageId,
                    versionNumber,
                  )
                }}
              />

              <ChatInput
                isLoading={
                  isLoading
                }
                onSend={
                  handleSend
                }
                onStop={
                  stopActiveRequest
                }
              />
            </>
          )}
        </div>
      </section>
      </main>

      <GuidedTour
        isOpen={guidedTourOpen}
        onComplete={() => {
          markGuidedTourCompleted()
          setGuidedTourOpen(false)
        }}
        onSkip={() => {
          markGuidedTourCompleted()
          setGuidedTourOpen(false)
        }}
      />

      {feedbackModal && (
        <FeedbackModal
          versionNumber={
            feedbackModal.versionNumber
          }
          existingFeedback={
            feedbackModal
              .existingFeedback
          }
          isSubmitting={
            activeOperationKind
            === "feedback"
          }
          onClose={() => {
            if (
              activeOperationKind
              !== "feedback"
            ) {
              setFeedbackModal(null)
            }
          }}
          onSubmit={(
            reason,
            comment,
          ) => {
            void submitNegativeFeedback(
              reason,
              comment,
            )
          }}
        />
      )}
    </>
  )
}
