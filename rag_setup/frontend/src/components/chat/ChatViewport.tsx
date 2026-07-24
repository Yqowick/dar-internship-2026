import {
  useEffect,
  useRef,
} from "react"

import {
  ScrollArea,
} from "@/components/ui/scroll-area"
import type {
  ChatMessage,
} from "@/types/chat"

import {
  ChatMessage as
    ChatMessageItem,
} from "./ChatMessage"
import {
  EmptyChatState,
} from "./EmptyChatState"
import {
  ThinkingIndicator,
} from "./ThinkingIndicator"

interface ChatViewportProps {
  messages: ChatMessage[]
  showThinkingIndicator:
    boolean
  thinkingLabel: string
  busyMessageId: string | null
  busyAction:
    | "regenerate"
    | "switch"
    | "feedback"
    | null
  interactionsDisabled: boolean
  onThumbsUp: (
    messageId: string,
  ) => void
  onThumbsDown: (
    messageId: string,
  ) => void
  onRegenerate: (
    messageId: string,
  ) => void
  onSwitchVersion: (
    messageId: string,
    versionNumber: number,
  ) => void
}

export function ChatViewport({
  messages,
  showThinkingIndicator,
  thinkingLabel,
  busyMessageId,
  busyAction,
  interactionsDisabled,
  onThumbsUp,
  onThumbsDown,
  onRegenerate,
  onSwitchVersion,
}: ChatViewportProps) {
  const bottomRef =
    useRef<HTMLDivElement | null>(
      null,
    )

  useEffect(() => {
    bottomRef.current
      ?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      })
  }, [
    messages,
    showThinkingIndicator,
    thinkingLabel,
  ])

  return (
    <ScrollArea className="min-h-0 flex-1">
      {messages.length === 0
        && !showThinkingIndicator ? (
          <EmptyChatState />
        ) : (
          <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
            {messages.map(
              (message) => (
                <ChatMessageItem
                  key={message.id}
                  message={message}
                  busyAction={
                    busyMessageId
                    === message.id
                      ? busyAction
                      : null
                  }
                  interactionsDisabled={
                    interactionsDisabled
                  }
                  onThumbsUp={
                    onThumbsUp
                  }
                  onThumbsDown={
                    onThumbsDown
                  }
                  onRegenerate={
                    onRegenerate
                  }
                  onSwitchVersion={
                    onSwitchVersion
                  }
                />
              ),
            )}

            {showThinkingIndicator && (
              <ThinkingIndicator
                label={thinkingLabel}
              />
            )}

            <div
              ref={bottomRef}
              aria-hidden="true"
            />
          </div>
        )}
    </ScrollArea>
  )
}
