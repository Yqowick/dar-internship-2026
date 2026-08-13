import {
  Bot,
  CircleCheck,
  CircleDashed,
  CircleHelp,
  CircleX,
  Database,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react"

import {
  BrandLogo,
} from "@/components/chat/BrandLogo"
import {
  Badge,
} from "@/components/ui/badge"
import {
  Button,
} from "@/components/ui/button"
import type {
  BackendStatus,
} from "@/types/chat"

interface AppHeaderProps {
  backendStatus: BackendStatus
  conversationTitle:
    string | null
  isSidebarOpen: boolean
  onToggleSidebar: () => void
  onReplayTour: () => void
}

const statusConfig = {
  checking: {
    label: "Checking services",
    icon: CircleDashed,
    className:
      "border-amber-200/80 bg-amber-50/90 text-amber-700",
  },
  online: {
    label: "RAG services online",
    icon: CircleCheck,
    className:
      "border-emerald-200/80 bg-emerald-50/90 text-emerald-700",
  },
  offline: {
    label: "Services offline",
    icon: CircleX,
    className:
      "border-red-200/80 bg-red-50/90 text-red-700",
  },
} satisfies Record<
  BackendStatus,
  {
    label: string
    icon: typeof CircleCheck
    className: string
  }
>

export function AppHeader({
  backendStatus,
  conversationTitle,
  isSidebarOpen,
  onToggleSidebar,
  onReplayTour,
}: AppHeaderProps) {
  const status =
    statusConfig[
      backendStatus
    ]

  const StatusIcon =
    status.icon

  return (
    <header
      data-tour="assistant-header"
      className="relative z-20 flex min-h-[78px] items-center justify-between gap-4 border-b border-border/70 bg-background/88 px-4 py-3.5 backdrop-blur-xl sm:px-6"
    >
      <div className="flex min-w-0 items-center gap-3">
        <Button
          data-tour="sidebar-toggle"
          type="button"
          variant="ghost"
          size="icon"
          className="size-10 shrink-0 rounded-xl border border-border/60 bg-card/75 text-muted-foreground shadow-sm hover:bg-accent hover:text-accent-foreground"
          onClick={onToggleSidebar}
          aria-label={
            isSidebarOpen
              ? "Hide chat history"
              : "Show chat history"
          }
          aria-expanded={
            isSidebarOpen
          }
          title={
            isSidebarOpen
              ? "Hide chat history"
              : "Show chat history"
          }
        >
          {isSidebarOpen ? (
            <PanelLeftClose
              className="size-5"
              aria-hidden="true"
            />
          ) : (
            <PanelLeftOpen
              className="size-5"
              aria-hidden="true"
            />
          )}
        </Button>

        <BrandLogo
          size="md"
          className="hidden sm:inline-flex"
        />

        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <h1 className="truncate text-base font-semibold tracking-tight text-foreground sm:text-lg">
              CIS Controls Assistant
            </h1>

            <Badge
              variant="secondary"
              className="hidden h-5 rounded-md px-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-primary md:inline-flex"
            >
              Local RAG
            </Badge>

            <Bot
              className="hidden size-4 text-primary/70 lg:block"
              aria-hidden="true"
            />
          </div>

          <p className="truncate text-xs text-muted-foreground sm:text-sm">
            {conversationTitle
              ?? (
                "Private · Source-grounded · CIS Controls v8"
              )}
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Badge
          variant="outline"
          className={
            `hidden h-8 gap-1.5 rounded-full px-3 text-[11px] font-medium shadow-sm sm:inline-flex `
            + status.className
          }
        >
          <StatusIcon
            className={
              `size-3.5 ${
                backendStatus
                  === "checking"
                  ? "animate-spin"
                  : ""
              }`
            }
            aria-hidden="true"
          />
          {status.label}
        </Badge>

        <Button
          data-tour="tour-replay"
          type="button"
          variant="outline"
          size="icon"
          className="size-10 rounded-xl border-border/70 bg-card/75 text-muted-foreground shadow-sm hover:border-primary/20 hover:bg-accent hover:text-primary"
          onClick={onReplayTour}
          aria-label="Replay guided tour"
          title="Replay guided tour"
        >
          <CircleHelp
            className="size-4"
            aria-hidden="true"
          />
        </Button>

        <div
          className="hidden size-10 items-center justify-center rounded-xl border border-border/70 bg-card/75 text-muted-foreground shadow-sm sm:flex"
          title="Weaviate vector database"
        >
          <Database
            className="size-4"
            aria-hidden="true"
          />
        </div>
      </div>
    </header>
  )
}
