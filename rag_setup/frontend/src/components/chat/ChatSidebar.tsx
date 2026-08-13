import {
  CheckCircle2,
  Clock3,
  DatabaseZap,
  LoaderCircle,
  MessageSquareText,
  MessagesSquare,
  Plus,
  Trash2,
  X,
} from "lucide-react"
import {
  useMemo,
} from "react"

import {
  BrandLogo,
} from "@/components/chat/BrandLogo"
import {
  Button,
} from "@/components/ui/button"
import {
  ScrollArea,
} from "@/components/ui/scroll-area"
import {
  Separator,
} from "@/components/ui/separator"
import {
  groupConversations,
} from "@/services/chatStorage"
import type {
  ChatConversation,
} from "@/types/chat"

interface ChatSidebarProps {
  conversations: ChatConversation[]
  activeConversationId:
    string | null
  isOpen: boolean
  isLoadingHistory: boolean
  historyError: string | null
  onClose: () => void
  onNewChat: () => void
  onSelectConversation: (
    conversationId: string,
  ) => void
  onDeleteConversation: (
    conversationId: string,
  ) => void
}

function formatUpdatedTime(
  timestamp: string,
): string {
  const date = new Date(timestamp)

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return ""
  }

  const now = new Date()
  const todayStart = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  )

  const dateStart = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  )

  const differenceInDays =
    Math.round(
      (
        todayStart.getTime()
        - dateStart.getTime()
      )
      / 86_400_000,
    )

  if (differenceInDays === 0) {
    return new Intl.DateTimeFormat(
      undefined,
      {
        hour: "2-digit",
        minute: "2-digit",
      },
    ).format(date)
  }

  if (differenceInDays === 1) {
    return "Yesterday"
  }

  if (differenceInDays < 7) {
    return new Intl.DateTimeFormat(
      undefined,
      {
        weekday: "short",
      },
    ).format(date)
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      month: "short",
      day: "numeric",
    },
  ).format(date)
}

export function ChatSidebar({
  conversations,
  activeConversationId,
  isOpen,
  isLoadingHistory,
  historyError,
  onClose,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
}: ChatSidebarProps) {
  const groups =
    useMemo(
      () =>
        groupConversations(
          conversations,
        ),
      [
        conversations,
      ],
    )

  const totalMessages =
    useMemo(
      () =>
        conversations.reduce(
          (
            total,
            conversation,
          ) =>
            total
            + conversation
              .messageCount,
          0,
        ),
      [conversations],
    )

  return (
    <>
      {isOpen && (
        <button
          type="button"
          aria-label="Close chat history"
          className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-[3px] lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        data-tour="chat-history"
        aria-hidden={!isOpen}
        className={
          `fixed inset-y-0 left-0 z-50 `
          + `flex w-[min(20rem,90vw)] `
          + `shrink-0 flex-col overflow-hidden `
          + `border-r border-sidebar-border/80 `
          + `bg-sidebar/96 shadow-2xl `
          + `backdrop-blur-2xl `
          + `transition-transform duration-200 `
          + `lg:static lg:inset-auto lg:z-auto `
          + `lg:h-full lg:translate-x-0 `
          + `lg:transition-[width,border-color] `
          + `lg:duration-300 lg:shadow-none ${
            isOpen
              ? (
                "translate-x-0 "
                + "lg:w-80 lg:border-r"
              )
              : (
                "-translate-x-full "
                + "lg:w-0 lg:border-r-0"
              )
          }`
        }
      >
        <div
          className={
            `flex h-full w-full shrink-0 `
            + `flex-col overflow-hidden `
            + `transition-opacity duration-150 `
            + `lg:w-80 ${
              isOpen
                ? "visible opacity-100"
                : (
                  "pointer-events-none "
                  + "invisible opacity-0"
                )
            }`
          }
        >
          <div className="relative overflow-hidden border-b border-sidebar-border/70 px-4 pb-4 pt-5">
            <div className="pointer-events-none absolute -right-10 -top-12 size-36 rounded-full bg-primary/8 blur-3xl" />
            <div className="pointer-events-none absolute -left-12 top-10 size-28 rounded-full bg-cyan-400/8 blur-3xl" />

            <div className="relative flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <BrandLogo size="sm" />

                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-semibold tracking-tight text-sidebar-foreground">
                      CIS Knowledge Hub
                    </p>

                    <span className="hidden rounded-md border border-primary/15 bg-primary/8 px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-[0.14em] text-primary sm:inline-flex">
                      Local
                    </span>
                  </div>

                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    Private MongoDB workspace
                  </p>
                </div>
              </div>

              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-8 shrink-0 rounded-lg border border-transparent text-muted-foreground hover:border-border hover:bg-card/75 lg:hidden"
                onClick={onClose}
                aria-label="Close sidebar"
              >
                <X
                  className="size-4"
                  aria-hidden="true"
                />
              </Button>
            </div>

            <Button
              data-tour="new-chat"
              type="button"
              className="brand-primary-button relative mt-4 h-11 w-full justify-between rounded-xl border-0 px-4 font-medium"
              onClick={onNewChat}
            >
              <span className="flex items-center gap-2">
                <Plus
                  className="size-4"
                  aria-hidden="true"
                />
                New conversation
              </span>

              <span className="rounded-md border border-white/15 bg-white/10 px-1.5 py-0.5 text-[9px] font-medium text-white/75">
                NEW
              </span>
            </Button>


            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-xl border border-sidebar-border/70 bg-card/55 px-3 py-2">
                <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <MessagesSquare
                    className="size-3.5 text-primary"
                    aria-hidden="true"
                  />
                  Conversations
                </div>

                <p className="mt-1 text-sm font-semibold text-sidebar-foreground">
                  {conversations.length}
                </p>
              </div>

              <div className="rounded-xl border border-sidebar-border/70 bg-card/55 px-3 py-2">
                <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <MessageSquareText
                    className="size-3.5 text-primary"
                    aria-hidden="true"
                  />
                  Messages
                </div>

                <p className="mt-1 text-sm font-semibold text-sidebar-foreground">
                  {totalMessages}
                </p>
              </div>
            </div>
          </div>

          <ScrollArea className="min-h-0 flex-1 overflow-hidden">
            <div className="w-full min-w-0 space-y-5 overflow-hidden px-3 py-4">
              {isLoadingHistory ? (
                <div
                  className="soft-panel flex items-center justify-center gap-2 rounded-xl p-4 text-xs text-muted-foreground"
                  role="status"
                >
                  <LoaderCircle
                    className="size-4 animate-spin text-primary"
                    aria-hidden="true"
                  />
                  Loading conversations…
                </div>
              ) : historyError ? (
                <div className="rounded-xl border border-red-200/80 bg-red-50/85 p-4 text-red-700">
                  <div className="flex items-center gap-2 text-xs font-medium">
                    <DatabaseZap
                      className="size-4"
                      aria-hidden="true"
                    />
                    History unavailable
                  </div>

                  <p className="mt-2 break-words text-[11px] leading-5">
                    {historyError}
                  </p>
                </div>
              ) : (
                conversations.length
                  === 0
              ) ? (
                <div className="soft-panel rounded-xl border-dashed p-5 text-center">
                  <div className="mx-auto flex size-10 items-center justify-center rounded-xl bg-primary/8 text-primary">
                    <MessageSquareText
                      className="size-5"
                      aria-hidden="true"
                    />
                  </div>

                  <p className="mt-3 text-xs font-medium">
                    No saved conversations
                  </p>

                  <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                    Send your first question to create a MongoDB-backed chat.
                  </p>
                </div>
              ) : (
                  groups.map(
                    (group) => (
                      <section
                        key={group.label}
                        className="min-w-0 space-y-2 overflow-hidden"
                      >
                        <div className="flex items-center justify-between px-1.5">
                          <h2 className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                            {group.label}
                          </h2>

                          <span className="rounded-full bg-muted px-2 py-0.5 text-[9px] font-medium text-muted-foreground">
                            {
                              group
                                .conversations
                                .length
                            }
                          </span>
                        </div>

                        <div className="space-y-1.5">
                          {group
                            .conversations
                            .map(
                              (
                                conversation,
                              ) => {
                                const isActive =
                                  conversation.id
                                  === activeConversationId

                                return (
                                  <article
                                    key={
                                      conversation.id
                                    }
                                    className={
                                      `group relative flex min-w-0 `
                                      + `items-center gap-2 overflow-hidden `
                                      + `rounded-2xl border p-1.5 transition-all ${
                                        isActive
                                          ? (
                                            "border-primary/20 "
                                            + "bg-gradient-to-br "
                                            + "from-primary/10 "
                                            + "to-cyan-400/5 "
                                            + "shadow-[0_8px_24px_rgba(22,74,108,0.09)]"
                                          )
                                          : (
                                            "border-transparent "
                                            + "hover:border-sidebar-border/90 "
                                            + "hover:bg-card/70 "
                                            + "hover:shadow-sm"
                                          )
                                      }`
                                    }
                                  >
                                    {isActive && (
                                      <span className="absolute inset-y-3 left-0 w-[3px] rounded-r-full bg-gradient-to-b from-primary to-cyan-500" />
                                    )}

                                    <button
                                      type="button"
                                      className="flex w-0 min-w-0 flex-1 items-start gap-2.5 overflow-hidden rounded-xl px-2 py-2 text-left"
                                      onClick={() =>
                                        onSelectConversation(
                                          conversation.id,
                                        )
                                      }
                                    >
                                      <span
                                        className={
                                          `mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl border ${
                                            isActive
                                              ? (
                                                "border-primary/15 "
                                                + "bg-primary/10 "
                                                + "text-primary"
                                              )
                                              : (
                                                "border-sidebar-border/80 "
                                                + "bg-card/70 "
                                                + "text-muted-foreground"
                                              )
                                          }`
                                        }
                                      >
                                        <MessageSquareText
                                          className="size-4"
                                          aria-hidden="true"
                                        />
                                      </span>

                                      <span className="min-w-0 flex-1">
                                        <span className="block overflow-hidden text-ellipsis whitespace-nowrap text-[12px] font-semibold text-sidebar-foreground">
                                          {
                                            conversation.title
                                          }
                                        </span>

                                        <span className="mt-1 block overflow-hidden text-ellipsis whitespace-nowrap text-[10px] leading-4 text-muted-foreground">
                                          {
                                            conversation
                                              .lastMessagePreview
                                          }
                                        </span>

                                        <span className="mt-1.5 flex items-center gap-2 text-[9px] text-muted-foreground/90">
                                          <span className="inline-flex items-center gap-1">
                                            <Clock3
                                              className="size-3"
                                              aria-hidden="true"
                                            />
                                            {
                                              formatUpdatedTime(
                                                conversation.updatedAt,
                                              )
                                            }
                                          </span>

                                          <span
                                            aria-hidden="true"
                                            className="size-1 rounded-full bg-muted-foreground/35"
                                          />

                                          <span>
                                            {
                                              conversation.messageCount
                                            } {
                                              conversation.messageCount
                                                === 1
                                                ? "message"
                                                : "messages"
                                            }
                                          </span>
                                        </span>
                                      </span>
                                    </button>

                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      className="mr-0.5 size-8 shrink-0 rounded-xl text-muted-foreground opacity-55 transition hover:bg-destructive/10 hover:text-destructive sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
                                      onClick={() =>
                                        onDeleteConversation(
                                          conversation.id,
                                        )
                                      }
                                      aria-label={
                                        `Delete ${conversation.title}`
                                      }
                                      title="Delete conversation"
                                    >
                                      <Trash2
                                        className="size-3.5"
                                        aria-hidden="true"
                                      />
                                    </Button>
                                  </article>
                                )
                              },
                            )}
                        </div>
                      </section>
                    ),
                  )
                )}
            </div>
          </ScrollArea>

          <Separator className="bg-sidebar-border/75" />

          <div className="px-4 py-3">
            <div className="flex items-center justify-between gap-3 rounded-xl border border-emerald-200/65 bg-emerald-50/65 px-3 py-2.5">
              <div className="flex min-w-0 items-center gap-2">
                <span className="relative flex size-2.5 shrink-0">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-35" />
                  <span className="relative inline-flex size-2.5 rounded-full bg-emerald-500" />
                </span>

                <div className="min-w-0">
                  <p className="truncate text-[10px] font-semibold text-emerald-800">
                    MongoDB synchronized
                  </p>

                  <p className="truncate text-[9px] text-emerald-700/75">
                    Chats, versions, citations & feedback
                  </p>
                </div>
              </div>

              <CheckCircle2
                className="size-4 shrink-0 text-emerald-600"
                aria-hidden="true"
              />
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
