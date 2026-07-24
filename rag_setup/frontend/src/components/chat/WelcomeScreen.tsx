import {
  ArrowUpRight,
  BookOpenCheck,
  LockKeyhole,
  MessageSquarePlus,
  Sparkles,
} from "lucide-react"

import {
  BrandLogo,
} from "@/components/chat/BrandLogo"
import {
  Button,
} from "@/components/ui/button"
import {
  Card,
  CardContent,
} from "@/components/ui/card"

interface WelcomeScreenProps {
  onStartNewChat: () => void
  onAskSuggestion: (
    question: string,
  ) => void
}

const suggestedQuestions = [
  {
    label: "Control overview",
    question: "What is CIS Control 1?",
  },
  {
    label: "Implementation groups",
    question: "Explain Implementation Group 1.",
  },
  {
    label: "Risk and purpose",
    question: "Why is enterprise asset inventory important?",
  },
  {
    label: "Safeguard detail",
    question: "What is Safeguard 1.1?",
  },
]

export function WelcomeScreen({
  onStartNewChat,
  onAskSuggestion,
}: WelcomeScreenProps) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full w-full max-w-5xl flex-col items-center justify-center px-5 py-12 text-center sm:px-8 lg:py-16">
        <div className="relative">
          <div className="absolute inset-0 scale-150 rounded-full bg-primary/10 blur-3xl" />
          <BrandLogo
            size="lg"
            className="relative"
          />
        </div>

        <div className="mt-7 max-w-3xl">
          <p className="brand-kicker mb-4 inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium">
            <LockKeyhole
              className="size-3.5"
              aria-hidden="true"
            />
            Private · Local · Source-grounded
          </p>

          <h2 className="text-balance text-3xl font-semibold tracking-[-0.035em] text-foreground sm:text-5xl">
            Cybersecurity guidance grounded in CIS Controls v8
          </h2>

          <p className="mx-auto mt-5 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
            Search the CIS Controls document, receive citation-backed answers,
            compare regenerated versions, and keep your complete research history locally.
          </p>
        </div>

        <Button
          data-tour="welcome-start"
          type="button"
          size="lg"
          className="brand-primary-button mt-8 h-12 gap-2 rounded-xl border-0 px-6"
          onClick={onStartNewChat}
        >
          <MessageSquarePlus
            className="size-4"
            aria-hidden="true"
          />
          Start a secure chat
          <ArrowUpRight
            className="size-4"
            aria-hidden="true"
          />
        </Button>

        <div
          data-tour="suggested-questions"
          className="mt-12 w-full"
        >
          <div className="mb-4 flex items-center justify-center gap-2 text-sm font-medium text-foreground">
            <BookOpenCheck
              className="size-4 text-primary"
              aria-hidden="true"
            />
            Suggested questions
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {suggestedQuestions.map(
              (item, index) => (
                <Card
                  key={item.question}
                  className="group gap-0 overflow-hidden border-border/70 bg-card/72 py-0 text-left shadow-[0_8px_24px_rgba(28,55,84,0.06)] backdrop-blur transition hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-[0_14px_30px_rgba(28,55,84,0.1)]"
                >
                  <CardContent className="p-0">
                    <button
                      type="button"
                      className="flex w-full items-center gap-3 p-4 text-left"
                      onClick={() =>
                        onAskSuggestion(
                          item.question,
                        )
                      }
                    >
                      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-xs font-semibold text-accent-foreground">
                        {String(index + 1).padStart(2, "0")}
                      </span>

                      <span className="min-w-0 flex-1">
                        <span className="block text-[10px] font-semibold uppercase tracking-[0.13em] text-primary/70">
                          {item.label}
                        </span>
                        <span className="mt-1 block text-sm font-medium leading-5 text-foreground">
                          {item.question}
                        </span>
                      </span>

                      <ArrowUpRight
                        className="size-4 shrink-0 text-muted-foreground transition group-hover:text-primary"
                        aria-hidden="true"
                      />
                    </button>
                  </CardContent>
                </Card>
              ),
            )}
          </div>
        </div>

        <div className="mt-8 flex items-center gap-2 text-[11px] text-muted-foreground">
          <Sparkles
            className="size-3.5 text-primary"
            aria-hidden="true"
          />
          Powered locally by Qwen, Weaviate, MongoDB, and FastAPI
        </div>
      </div>
    </div>
  )
}
