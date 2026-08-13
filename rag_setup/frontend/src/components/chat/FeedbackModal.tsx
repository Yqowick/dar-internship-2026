import {
  MessageSquareWarning,
  X,
} from "lucide-react"
import {
  useEffect,
  useState,
} from "react"

import {
  Button,
} from "@/components/ui/button"
import {
  Textarea,
} from "@/components/ui/textarea"
import type {
  FeedbackReason,
  MessageFeedback,
} from "@/types/chat"

interface FeedbackModalProps {
  versionNumber: number
  existingFeedback:
    MessageFeedback | null
  isSubmitting: boolean
  onClose: () => void
  onSubmit: (
    reason: FeedbackReason,
    comment: string | null,
  ) => void
}

const reasons: Array<{
  value: FeedbackReason
  label: string
}> = [
  {
    value: "incorrect_answer",
    label: "Incorrect answer",
  },
  {
    value: "missing_information",
    label: "Missing information",
  },
  {
    value: "citation_problem",
    label: "Citation problem",
  },
  {
    value: "unclear_answer",
    label: "Unclear answer",
  },
  {
    value: "not_relevant",
    label: "Not relevant",
  },
  {
    value: "other",
    label: "Other",
  },
]

export function FeedbackModal({
  versionNumber,
  existingFeedback,
  isSubmitting,
  onClose,
  onSubmit,
}: FeedbackModalProps) {
  const [reason, setReason] =
    useState<FeedbackReason | null>(
      existingFeedback?.rating
        === "down"
        ? existingFeedback.reason
        : null,
    )

  const [comment, setComment] =
    useState(
      existingFeedback?.rating
        === "down"
        ? existingFeedback.comment
          ?? ""
        : "",
    )

  useEffect(() => {
    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (
        event.key === "Escape"
        && !isSubmitting
      ) {
        onClose()
      }
    }

    window.addEventListener(
      "keydown",
      handleKeyDown,
    )

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      )
    }
  }, [isSubmitting, onClose])

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (
          event.target === event.currentTarget
          && !isSubmitting
        ) {
          onClose()
        }
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="feedback-title"
        className="w-full max-w-lg rounded-2xl border border-border/70 bg-background/98 p-5 shadow-[0_28px_80px_rgba(15,35,60,0.28)] backdrop-blur-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="brand-gradient flex size-10 shrink-0 items-center justify-center rounded-xl text-white shadow-sm">
              <MessageSquareWarning
                className="size-5"
                aria-hidden="true"
              />
            </div>

            <div>
              <h2
                id="feedback-title"
                className="font-semibold"
              >
                What could be improved?
              </h2>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                Your feedback applies only
                to response version {versionNumber}.
              </p>
            </div>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 shrink-0"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close feedback dialog"
          >
            <X
              className="size-4"
              aria-hidden="true"
            />
          </Button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {reasons.map((item) => {
            const selected =
              reason === item.value

            return (
              <button
                key={item.value}
                type="button"
                className={
                  `rounded-full border px-3 py-1.5 text-xs transition ${
                    selected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "bg-background hover:bg-muted"
                  }`
                }
                onClick={() =>
                  setReason(item.value)
                }
                disabled={isSubmitting}
              >
                {item.label}
              </button>
            )
          })}
        </div>

        <div className="mt-5">
          <label
            htmlFor="feedback-comment"
            className="text-xs font-medium"
          >
            Additional comment
            <span className="ml-1 font-normal text-muted-foreground">
              (optional)
            </span>
          </label>

          <Textarea
            id="feedback-comment"
            value={comment}
            onChange={(event) =>
              setComment(event.target.value)
            }
            maxLength={1000}
            rows={4}
            className="mt-2 resize-none"
            placeholder="Tell us what was wrong or missing…"
            disabled={isSubmitting}
          />
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>

          <Button
            type="button"
            onClick={() => {
              if (reason) {
                onSubmit(
                  reason,
                  comment.trim() || null,
                )
              }
            }}
            disabled={
              reason === null
              || isSubmitting
            }
          >
            {isSubmitting
              ? "Saving…"
              : "Submit feedback"}
          </Button>
        </div>
      </section>
    </div>
  )
}
