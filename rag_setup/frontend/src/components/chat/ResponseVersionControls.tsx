import {
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  LoaderCircle,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react"
import {
  useState,
} from "react"

import {
  Button,
} from "@/components/ui/button"
import type {
  MessageFeedback,
} from "@/types/chat"

interface ResponseVersionControlsProps {
  content: string
  feedback: MessageFeedback | null
  activeVersionNumber: number
  versionCount: number
  busyAction:
    | "regenerate"
    | "switch"
    | "feedback"
    | null
  disabled: boolean
  onThumbsUp: () => void
  onThumbsDown: () => void
  onRegenerate: () => void
  onSwitchVersion: (
    versionNumber: number,
  ) => void
}

export function ResponseVersionControls({
  content,
  feedback,
  activeVersionNumber,
  versionCount,
  busyAction,
  disabled,
  onThumbsUp,
  onThumbsDown,
  onRegenerate,
  onSwitchVersion,
}: ResponseVersionControlsProps) {
  const [copied, setCopied] =
    useState(false)

  const isRegenerating =
    busyAction === "regenerate"
  const isSwitching =
    busyAction === "switch"
  const isSavingFeedback =
    busyAction === "feedback"
  const isBusy =
    busyAction !== null

  const canGoPrevious =
    activeVersionNumber > 1
  const canGoNext =
    activeVersionNumber < versionCount

  const copyResponse = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      window.setTimeout(
        () => setCopied(false),
        1400,
      )
    } catch {
      setCopied(false)
    }
  }

  const iconButtonClass =
    "size-9 rounded-lg text-muted-foreground transition hover:bg-accent hover:text-primary"

  return (
    <div
      data-tour="response-actions"
      className="soft-panel flex max-w-full items-center gap-1 overflow-x-auto rounded-xl px-2 py-1.5 shadow-[0_6px_18px_rgba(29,55,83,0.06)]"
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={iconButtonClass}
        onClick={() => {
          void copyResponse()
        }}
        disabled={disabled}
        aria-label="Copy response"
        title={copied ? "Copied" : "Copy response"}
      >
        {copied ? (
          <Check className="size-4 text-emerald-600" aria-hidden="true" />
        ) : (
          <Copy className="size-4" aria-hidden="true" />
        )}
      </Button>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={`${iconButtonClass} ${
          feedback?.rating === "up"
            ? "bg-emerald-50 text-emerald-700"
            : ""
        }`}
        onClick={onThumbsUp}
        disabled={
          disabled
          || isBusy
          || feedback?.rating === "up"
        }
        aria-label="Helpful response"
        title="Helpful"
      >
        {isSavingFeedback ? (
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <ThumbsUp
            className="size-4"
            fill={feedback?.rating === "up" ? "currentColor" : "none"}
            aria-hidden="true"
          />
        )}
      </Button>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={`${iconButtonClass} ${
          feedback?.rating === "down"
            ? "bg-rose-50 text-rose-700"
            : ""
        }`}
        onClick={onThumbsDown}
        disabled={disabled || isBusy}
        aria-label="Not helpful response"
        title={
          feedback?.rating === "down"
            ? "Edit negative feedback"
            : "Not helpful"
        }
      >
        <ThumbsDown
          className="size-4"
          fill={feedback?.rating === "down" ? "currentColor" : "none"}
          aria-hidden="true"
        />
      </Button>

      <div className="mx-1 h-5 w-px shrink-0 bg-border" />

      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={iconButtonClass}
        disabled={disabled || isBusy}
        onClick={onRegenerate}
        aria-label="Regenerate response"
        title="Regenerate response"
      >
        {isRegenerating ? (
          <LoaderCircle className="size-4 animate-spin text-primary" aria-hidden="true" />
        ) : (
          <RefreshCw className="size-4" aria-hidden="true" />
        )}
      </Button>

      <div className="mx-1 h-5 w-px shrink-0 bg-border" />

      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={iconButtonClass}
        disabled={disabled || isBusy || !canGoPrevious}
        onClick={() =>
          onSwitchVersion(activeVersionNumber - 1)
        }
        aria-label="Previous response version"
        title="Previous version"
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
      </Button>

      <span className="inline-flex min-w-14 shrink-0 items-center justify-center rounded-md bg-muted/70 px-2 py-1 text-[10px] font-semibold text-muted-foreground">
        {isSwitching ? (
          <LoaderCircle className="size-3.5 animate-spin" aria-label="Switching versions" />
        ) : (
          `${activeVersionNumber} / ${versionCount}`
        )}
      </span>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={iconButtonClass}
        disabled={disabled || isBusy || !canGoNext}
        onClick={() =>
          onSwitchVersion(activeVersionNumber + 1)
        }
        aria-label="Next response version"
        title="Next version"
      >
        <ChevronRight className="size-4" aria-hidden="true" />
      </Button>
    </div>
  )
}
