import {
  ArrowLeft,
  ArrowRight,
  Check,
  X,
} from "lucide-react"
import {
  useEffect,
  useMemo,
  useState,
} from "react"
import {
  createPortal,
} from "react-dom"

import {
  Button,
} from "@/components/ui/button"

interface GuidedTourProps {
  isOpen: boolean
  onComplete: () => void
  onSkip: () => void
}

interface TourStep {
  target: string
  fallbackTargets?: string[]
  title: string
  description: string
}

interface TargetRectangle {
  top: number
  left: number
  width: number
  height: number
  right: number
  bottom: number
}

const TOUR_STEPS: TourStep[] = [
  {
    target:
      '[data-tour="sidebar-toggle"]',
    title: "Toggle chat history",
    description:
      "Use this button to open or close your MongoDB-backed conversation history.",
  },
  {
    target:
      '[data-tour="new-chat"]',
    fallbackTargets: [
      '[data-tour="chat-history"]',
      '[data-tour="sidebar-toggle"]',
    ],
    title: "Start a new conversation",
    description:
      "Create a separate chat. Its MongoDB record is created after you send the first question.",
  },
  {
    target:
      '[data-tour="chat-history"]',
    fallbackTargets: [
      '[data-tour="sidebar-toggle"]',
    ],
    title: "Resume saved conversations",
    description:
      "Select any saved thread to reload its messages, citations, response versions, and feedback.",
  },
  {
    target:
      '[data-tour="question-input"]',
    fallbackTargets: [
      '[data-tour="welcome-start"]',
      '[data-tour="suggested-questions"]',
    ],
    title: "Ask a grounded question",
    description:
      "Start a chat, choose a suggested question, or type directly in the composer to ask about CIS Controls v8.",
  },
  {
    target:
      '[data-tour="inline-citation"]',
    fallbackTargets: [
      '[data-tour="suggested-questions"]',
      '[data-tour="question-input"]',
      '[data-tour="welcome-start"]',
    ],
    title: "Verify inline citations",
    description:
      "After an answer is generated, hover over or click citations such as [1] to verify the supporting source.",
  },
  {
    target:
      '[data-tour="source-metadata"]',
    fallbackTargets: [
      '[data-tour="inline-citation"]',
      '[data-tour="question-input"]',
      '[data-tour="suggested-questions"]',
    ],
    title: "Inspect source metadata",
    description:
      "Each completed answer provides expandable source details including document, page, section, chunk ID, and snippet.",
  },
  {
    target:
      '[data-tour="response-actions"]',
    fallbackTargets: [
      '[data-tour="source-metadata"]',
      '[data-tour="question-input"]',
      '[data-tour="suggested-questions"]',
    ],
    title: "Manage every response",
    description:
      "Copy answers, submit feedback, regenerate a response, and move between saved response versions.",
  },
  {
    target:
      '[data-tour="tour-replay"]',
    title: "Replay the tour anytime",
    description:
      "Use this help button whenever you want to review all eight guided-tour steps again.",
  },
]

function getTargetRectangle(
  element: HTMLElement,
): TargetRectangle {
  const rectangle =
    element.getBoundingClientRect()

  return {
    top: rectangle.top,
    left: rectangle.left,
    width: rectangle.width,
    height: rectangle.height,
    right: rectangle.right,
    bottom: rectangle.bottom,
  }
}

function clamp(
  value: number,
  minimum: number,
  maximum: number,
): number {
  return Math.min(
    Math.max(value, minimum),
    maximum,
  )
}

export function GuidedTour({
  isOpen,
  onComplete,
  onSkip,
}: GuidedTourProps) {
  const [
    availableSteps,
    setAvailableSteps,
  ] = useState<TourStep[]>([])

  const [
    currentStepIndex,
    setCurrentStepIndex,
  ] = useState(0)

  const [
    targetRectangle,
    setTargetRectangle,
  ] = useState<
    TargetRectangle | null
  >(null)

  useEffect(() => {
    if (!isOpen) {
      setAvailableSteps([])
      setCurrentStepIndex(0)
      setTargetRectangle(null)
      return
    }

    const timer =
      window.setTimeout(
        () => {
          setAvailableSteps(
            TOUR_STEPS,
          )
          setCurrentStepIndex(0)
        },
        220,
      )

    return () => {
      window.clearTimeout(timer)
    }
  }, [
    isOpen,
    onComplete,
  ])

  const currentStep =
    availableSteps[
      currentStepIndex
    ] ?? null

  useEffect(() => {
    if (
      !isOpen
      || !currentStep
    ) {
      return
    }

    const selectors = [
      currentStep.target,
      ...(
        currentStep
          .fallbackTargets
        ?? []
      ),
      '[data-tour="assistant-header"]',
    ]

    const target =
      selectors
        .map(
          (selector) =>
            document.querySelector<
              HTMLElement
            >(selector),
        )
        .find(
          (
            element,
          ): element is HTMLElement => {
            if (!element) {
              return false
            }

            const rectangle =
              element
                .getBoundingClientRect()

            return (
              rectangle.width > 0
              && rectangle.height > 0
            )
          },
        )

    if (!target) {
      return
    }

    const updatePosition =
      () => {
        setTargetRectangle(
          getTargetRectangle(
            target,
          ),
        )
      }

    target.scrollIntoView({
      behavior: "smooth",
      block: "center",
      inline: "nearest",
    })

    updatePosition()

    const delayedUpdate =
      window.setTimeout(
        updatePosition,
        350,
      )

    window.addEventListener(
      "resize",
      updatePosition,
    )

    window.addEventListener(
      "scroll",
      updatePosition,
      true,
    )

    return () => {
      window.clearTimeout(
        delayedUpdate,
      )

      window.removeEventListener(
        "resize",
        updatePosition,
      )

      window.removeEventListener(
        "scroll",
        updatePosition,
        true,
      )
    }
  }, [
    isOpen,
    currentStep,
  ])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (event.key === "Escape") {
        onSkip()
      }

      if (
        event.key === "ArrowRight"
        && currentStepIndex
          < availableSteps.length - 1
      ) {
        setCurrentStepIndex(
          (index) => index + 1,
        )
      }

      if (
        event.key === "ArrowLeft"
        && currentStepIndex > 0
      ) {
        setCurrentStepIndex(
          (index) => index - 1,
        )
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
  }, [
    isOpen,
    currentStepIndex,
    availableSteps.length,
    onSkip,
  ])

  const popoverStyle =
    useMemo(() => {
      if (!targetRectangle) {
        return {}
      }

      const viewportWidth =
        window.innerWidth
      const viewportHeight =
        window.innerHeight
      const viewportMargin = 12
      const targetGap = 16
      const estimatedPopoverHeight = 250
      const popoverWidth =
        Math.min(
          360,
          viewportWidth
            - viewportMargin * 2,
        )

      const maximumLeft =
        Math.max(
          viewportMargin,
          viewportWidth
            - popoverWidth
            - viewportMargin,
        )

      const maximumTop =
        Math.max(
          viewportMargin,
          viewportHeight
            - estimatedPopoverHeight
            - viewportMargin,
        )

      const centeredLeft =
        clamp(
          targetRectangle.left
            + targetRectangle.width / 2
            - popoverWidth / 2,
          viewportMargin,
          maximumLeft,
        )

      const centeredTop =
        clamp(
          targetRectangle.top
            + targetRectangle.height / 2
            - estimatedPopoverHeight / 2,
          viewportMargin,
          maximumTop,
        )

      const fitsOnRight =
        targetRectangle.right
          + targetGap
          + popoverWidth
        <= viewportWidth
          - viewportMargin

      if (fitsOnRight) {
        return {
          left:
            targetRectangle.right
            + targetGap,
          top: centeredTop,
          width: popoverWidth,
        }
      }

      const fitsOnLeft =
        targetRectangle.left
          - targetGap
          - popoverWidth
        >= viewportMargin

      if (fitsOnLeft) {
        return {
          left:
            targetRectangle.left
            - targetGap
            - popoverWidth,
          top: centeredTop,
          width: popoverWidth,
        }
      }

      const fitsBelow =
        targetRectangle.bottom
          + targetGap
          + estimatedPopoverHeight
        <= viewportHeight
          - viewportMargin

      if (fitsBelow) {
        return {
          left: centeredLeft,
          top:
            targetRectangle.bottom
            + targetGap,
          width: popoverWidth,
        }
      }

      const fitsAbove =
        targetRectangle.top
          - targetGap
          - estimatedPopoverHeight
        >= viewportMargin

      if (fitsAbove) {
        return {
          left: centeredLeft,
          top:
            targetRectangle.top
            - targetGap
            - estimatedPopoverHeight,
          width: popoverWidth,
        }
      }

      return {
        left: centeredLeft,
        top: clamp(
          viewportHeight
            - estimatedPopoverHeight
            - viewportMargin,
          viewportMargin,
          maximumTop,
        ),
        width: popoverWidth,
      }
    }, [targetRectangle])

  if (
    !isOpen
    || !currentStep
    || !targetRectangle
  ) {
    return null
  }

  const isLastStep =
    currentStepIndex
    === availableSteps.length - 1

  const highlightPadding = 7

  return createPortal(
    <div
      className="fixed inset-0 z-[100]"
      role="dialog"
      aria-modal="true"
      aria-label="Application guided tour"
    >
      <div
        aria-hidden="true"
        className="fixed inset-0"
        onClick={onSkip}
      />

      <div
        aria-hidden="true"
        className="pointer-events-none fixed rounded-xl border-2 border-cyan-200 transition-all duration-200"
        style={{
          top:
            targetRectangle.top
            - highlightPadding,
          left:
            targetRectangle.left
            - highlightPadding,
          width:
            targetRectangle.width
            + highlightPadding * 2,
          height:
            targetRectangle.height
            + highlightPadding * 2,
          boxShadow:
            "0 0 0 9999px rgba(15, 23, 42, 0.66)",
        }}
      />

      <section
        className="fixed max-h-[calc(100vh-1.5rem)] overflow-y-auto rounded-2xl border border-border/70 bg-background/98 p-4 shadow-[0_28px_80px_rgba(15,35,60,0.32)] backdrop-blur-xl"
        style={popoverStyle}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Step {
                currentStepIndex + 1
              } of {
                availableSteps.length
              }
            </p>

            <h2 className="mt-1 text-base font-semibold">
              {currentStep.title}
            </h2>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 shrink-0"
            onClick={onSkip}
            aria-label="Close guided tour"
            title="Close tour"
          >
            <X
              className="size-4"
              aria-hidden="true"
            />
          </Button>
        </div>

        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          {currentStep.description}
        </p>

        <div className="mt-5 flex items-center justify-between gap-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onSkip}
          >
            Skip tour
          </Button>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={
                currentStepIndex === 0
              }
              onClick={() =>
                setCurrentStepIndex(
                  (index) =>
                    Math.max(
                      index - 1,
                      0,
                    ),
                )
              }
            >
              <ArrowLeft
                className="size-4"
                aria-hidden="true"
              />
              Back
            </Button>

            <Button
              type="button"
              size="sm"
              onClick={() => {
                if (isLastStep) {
                  onComplete()
                  return
                }

                setCurrentStepIndex(
                  (index) =>
                    Math.min(
                      index + 1,
                      availableSteps.length
                        - 1,
                    ),
                )
              }}
            >
              {isLastStep ? (
                <>
                  <Check
                    className="size-4"
                    aria-hidden="true"
                  />
                  Finish
                </>
              ) : (
                <>
                  Next
                  <ArrowRight
                    className="size-4"
                    aria-hidden="true"
                  />
                </>
              )}
            </Button>
          </div>
        </div>
      </section>
    </div>,
    document.body,
  )
}
