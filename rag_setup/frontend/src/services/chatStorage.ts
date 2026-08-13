import type {
  ChatConversation,
} from "@/types/chat"

export interface ConversationGroup {
  label: string
  conversations: ChatConversation[]
}

function toTimestamp(
  value: string,
): number {
  const timestamp =
    new Date(value).getTime()

  return Number.isFinite(timestamp)
    ? timestamp
    : 0
}

export function sortConversations(
  conversations: ChatConversation[],
): ChatConversation[] {
  return [...conversations].sort(
    (left, right) =>
      toTimestamp(right.updatedAt)
      - toTimestamp(left.updatedAt),
  )
}

export function createConversationTitle(
  question: string,
): string {
  const cleanedQuestion =
    question
      .replace(/\s+/g, " ")
      .trim()
      .replace(/[?!.]+$/, "")

  const title =
    cleanedQuestion.length > 52
      ? `${cleanedQuestion.slice(
          0,
          49,
        ).trim()}…`
      : cleanedQuestion

  return title || "New conversation"
}

function startOfLocalDay(
  date: Date,
): Date {
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  )
}

export function groupConversations(
  conversations: ChatConversation[],
): ConversationGroup[] {
  const today =
    startOfLocalDay(new Date())

  const yesterday =
    new Date(today)

  yesterday.setDate(
    yesterday.getDate() - 1,
  )

  const lastWeek =
    new Date(today)

  lastWeek.setDate(
    lastWeek.getDate() - 7,
  )

  const groups: Record<
    "Today"
    | "Yesterday"
    | "Previous 7 days"
    | "Older",
    ChatConversation[]
  > = {
    Today: [],
    Yesterday: [],
    "Previous 7 days": [],
    Older: [],
  }

  for (
    const conversation
    of sortConversations(
      conversations,
    )
  ) {
    const updatedAt =
      new Date(
        conversation.updatedAt,
      )

    if (updatedAt >= today) {
      groups.Today.push(
        conversation,
      )
    } else if (
      updatedAt >= yesterday
    ) {
      groups.Yesterday.push(
        conversation,
      )
    } else if (
      updatedAt >= lastWeek
    ) {
      groups[
        "Previous 7 days"
      ].push(conversation)
    } else {
      groups.Older.push(
        conversation,
      )
    }
  }

  return Object.entries(groups)
    .filter(
      (
        [, groupedConversations],
      ) =>
        groupedConversations
          .length > 0,
    )
    .map(
      ([
        label,
        groupedConversations,
      ]) => ({
        label,
        conversations:
          groupedConversations,
      }),
    )
}
