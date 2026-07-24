import {
  useState,
} from "react"
import {
  LockKeyhole,
  SendHorizontal,
  Square,
} from "lucide-react"

import {
  Button,
} from "@/components/ui/button"
import {
  Textarea,
} from "@/components/ui/textarea"

interface ChatInputProps {
  isLoading: boolean
  onSend: (
    question: string,
  ) => Promise<void>
  onStop: () => void
}

export function ChatInput({
  isLoading,
  onSend,
  onStop,
}: ChatInputProps) {
  const [question, setQuestion] =
    useState("")

  const submitQuestion =
    async () => {
      const cleanedQuestion =
        question.trim()

      if (
        !cleanedQuestion
        || isLoading
      ) {
        return
      }

      setQuestion("")
      await onSend(cleanedQuestion)
    }

  return (
    <div className="border-t border-border/65 bg-background/82 px-4 py-4 backdrop-blur-xl sm:px-6">
      <form
        data-tour="question-input"
        className="mx-auto w-full max-w-4xl"
        onSubmit={(event) => {
          event.preventDefault()
          void submitQuestion()
        }}
      >
        <div className="composer-shell flex items-end gap-2 rounded-2xl p-2 transition">
          <Textarea
            value={question}
            onChange={(event) =>
              setQuestion(
                event.target.value,
              )
            }
            onKeyDown={(event) => {
              if (
                event.key === "Enter"
                && !event.shiftKey
                && !event.nativeEvent.isComposing
              ) {
                event.preventDefault()
                void submitQuestion()
              }
            }}
            placeholder={
              isLoading
                ? "Generating a grounded response…"
                : "Ask about a CIS Control, safeguard, or implementation group…"
            }
            aria-label="Question"
            rows={1}
            disabled={isLoading}
            className="max-h-40 min-h-11 resize-none border-0 bg-transparent px-3 py-2.5 text-[15px] shadow-none placeholder:text-muted-foreground/70 focus-visible:ring-0"
          />

          {isLoading ? (
            <Button
              type="button"
              size="icon"
              variant="destructive"
              className="size-11 shrink-0 rounded-xl shadow-sm"
              onClick={onStop}
              aria-label="Stop response"
              title="Stop response"
            >
              <Square
                className="size-4"
                fill="currentColor"
                aria-hidden="true"
              />
            </Button>
          ) : (
            <Button
              type="submit"
              size="icon"
              className="brand-primary-button size-11 shrink-0 rounded-xl border-0"
              disabled={!question.trim()}
              aria-label="Send question"
              title="Send question"
            >
              <SendHorizontal
                className="size-4"
                aria-hidden="true"
              />
            </Button>
          )}
        </div>

        <div className="mt-2 flex items-center justify-center gap-1.5 text-[10px] text-muted-foreground">
          <LockKeyhole
            className="size-3 text-primary/70"
            aria-hidden="true"
          />
          Answers use only the local CIS Controls knowledge base · Enter to send
        </div>
      </form>
    </div>
  )
}
