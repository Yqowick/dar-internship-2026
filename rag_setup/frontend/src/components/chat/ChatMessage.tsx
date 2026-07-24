import {
  AlertTriangle,
  Bot,
  CircleStop,
  UserRound,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import {
  Avatar,
  AvatarFallback,
} from "@/components/ui/avatar"
import type {
  ChatMessage as
    ChatMessageModel,
  ChatSource,
} from "@/types/chat"

import {
  CitationTooltip,
} from "./CitationTooltip"
import {
  ResponseVersionControls,
} from "./ResponseVersionControls"
import {
  SourceMetadataAccordion,
} from "./SourceMetadataAccordion"

interface ChatMessageProps {
  message: ChatMessageModel
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

function formatTime(
  timestamp: string,
): string {
  return new Intl.DateTimeFormat(
    undefined,
    {
      hour: "2-digit",
      minute: "2-digit",
    },
  ).format(
    new Date(timestamp),
  )
}

function citationMarkdown(
  content: string,
): string {
  return content
    .replace(
      /\[Source\s+(\d+)\]/gi,
      "[$1](#citation-$1)",
    )
    .replace(
      /\[(\d+)\](?!\()/g,
      "[$1](#citation-$1)",
    )
}

function findCitationSource(
  href: string | undefined,
  sources: ChatSource[],
): ChatSource | null {
  if (
    !href
    || !href.startsWith(
      "#citation-",
    )
  ) {
    return null
  }

  const sourceId =
    Number.parseInt(
      href.slice(
        "#citation-".length,
      ),
      10,
    )

  if (
    !Number.isInteger(sourceId)
  ) {
    return null
  }

  return (
    sources.find(
      (source) =>
        source.sourceId
        === sourceId,
    )
    ?? null
  )
}

export function ChatMessage({
  message,
  busyAction,
  interactionsDisabled,
  onThumbsUp,
  onThumbsDown,
  onRegenerate,
  onSwitchVersion,
}: ChatMessageProps) {
  const isUser =
    message.role === "user"

  const isError =
    message.status === "error"

  const isStreaming =
    message.status === "streaming"

  const isStopped =
    message.status === "stopped"

  const sources =
    message.sources ?? []

  const versionCount =
    Math.max(
      message.versionCount ?? 0,
      message.activeVersionId
        ? 1
        : 0,
    )

  const activeVersionNumber =
    message.activeVersionNumber
    ?? (
      versionCount > 0
        ? versionCount
        : 1
    )

  if (
    isStreaming
    && message.content.length === 0
  ) {
    return null
  }

  return (
    <article
      className={
        `flex gap-3 ${
          isUser
            ? "flex-row-reverse"
            : "flex-row"
        }`
      }
    >
      <Avatar className="mt-0.5 size-9 shrink-0 border border-border/70 shadow-sm">
        <AvatarFallback
          className={
            isUser
              ? (
                "brand-gradient "
                + "text-white"
              )
              : (
                "bg-accent "
                + "text-primary"
              )
          }
        >
          {isUser ? (
            <UserRound
              className="size-4"
              aria-hidden="true"
            />
          ) : (
            <Bot
              className="size-4"
              aria-hidden="true"
            />
          )}
        </AvatarFallback>
      </Avatar>

      <div
        className={
          `min-w-0 max-w-[88%] `
          + `space-y-2 sm:max-w-[78%] ${
            isUser
              ? "items-end"
              : "items-start"
          }`
        }
      >
        <div
          className={
            `rounded-2xl px-4 py-3 `
            + `text-sm leading-7 shadow-sm ${
              isUser
                ? (
                  "message-user rounded-tr-md"
                )
                : isError
                  ? (
                    "rounded-tl-md border "
                    + "border-red-200 "
                    + "bg-red-50 "
                    + "text-red-800"
                  )
                  : (
                    "message-assistant rounded-tl-md "
                    + "text-card-foreground"
                  )
            }`
          }
        >
          {isError && (
            <div className="mb-2 flex items-center gap-2 font-medium">
              <AlertTriangle
                className="size-4"
                aria-hidden="true"
              />
              Request failed
            </div>
          )}

          {isUser ? (
            <p className="whitespace-pre-wrap">
              {message.content}
            </p>
          ) : (
            <>
              <ReactMarkdown
                remarkPlugins={[
                  remarkGfm,
                ]}
                components={{
                  h1: ({
                    children,
                  }) => (
                    <h1 className="mb-2 text-lg font-semibold tracking-tight text-foreground">
                      {children}
                    </h1>
                  ),
                  h2: ({
                    children,
                  }) => (
                    <h2 className="mb-2 text-base font-semibold tracking-tight text-foreground">
                      {children}
                    </h2>
                  ),
                  p: ({
                    children,
                  }) => (
                    <p className="mb-3 last:mb-0">
                      {children}
                    </p>
                  ),
                  ul: ({
                    children,
                  }) => (
                    <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">
                      {children}
                    </ul>
                  ),
                  ol: ({
                    children,
                  }) => (
                    <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">
                      {children}
                    </ol>
                  ),
                  code: ({
                    children,
                  }) => (
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                      {children}
                    </code>
                  ),
                  pre: ({
                    children,
                  }) => (
                    <pre className="mb-3 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-50 last:mb-0">
                      {children}
                    </pre>
                  ),
                  a: ({
                    href,
                    children,
                  }) => {
                    const citationSource =
                      findCitationSource(
                        href,
                        sources,
                      )

                    if (
                      citationSource
                    ) {
                      return (
                        <CitationTooltip
                          messageId={
                            message.id
                          }
                          source={
                            citationSource
                          }
                        />
                      )
                    }

                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-primary underline underline-offset-4"
                      >
                        {children}
                      </a>
                    )
                  },
                }}
              >
                {citationMarkdown(
                  message.content,
                )}
              </ReactMarkdown>

              {isStreaming && (
                <span
                  className="ml-1 inline-block h-4 w-1 animate-pulse bg-current align-middle"
                  aria-hidden="true"
                />
              )}
            </>
          )}
        </div>

        {!isUser
          && sources.length > 0
          && (
            <SourceMetadataAccordion
              messageId={
                message.id
              }
              sources={sources}
            />
          )}

        {!isUser
          && versionCount > 0
          && message.status
            !== "error"
          && (
            <ResponseVersionControls
              content={
                message.content
              }
              feedback={
                message.feedback
                ?? null
              }
              activeVersionNumber={
                activeVersionNumber
              }
              versionCount={
                versionCount
              }
              busyAction={
                busyAction
              }
              disabled={
                interactionsDisabled
              }
              onThumbsUp={() =>
                onThumbsUp(
                  message.id,
                )
              }
              onThumbsDown={() =>
                onThumbsDown(
                  message.id,
                )
              }
              onRegenerate={() =>
                onRegenerate(
                  message.id,
                )
              }
              onSwitchVersion={(
                versionNumber,
              ) =>
                onSwitchVersion(
                  message.id,
                  versionNumber,
                )
              }
            />
          )}

        <div
          className={
            `flex items-center gap-2 px-1 `
            + `text-[11px] text-muted-foreground ${
              isUser
                ? "justify-end"
                : "justify-start"
            }`
          }
        >
          <span>
            {formatTime(
              message.createdAt,
            )}
          </span>

          {isStopped && (
            <span className="inline-flex items-center gap-1">
              <CircleStop
                className="size-3"
                aria-hidden="true"
              />
              Stopped
            </span>
          )}
        </div>
      </div>
    </article>
  )
}
