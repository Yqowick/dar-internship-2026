import type {
  ChatSource,
} from "@/types/chat"

interface CitationTooltipProps {
  messageId: string
  source: ChatSource
}

function formatPages(
  source: ChatSource,
): string {
  if (source.pageNumber === null) {
    return "Page unavailable"
  }

  if (
    source.endPageNumber === null
    || source.endPageNumber
      === source.pageNumber
  ) {
    return `Page ${source.pageNumber}`
  }

  return (
    `Pages ${source.pageNumber}`
    + `–${source.endPageNumber}`
  )
}

export function CitationTooltip({
  messageId,
  source,
}: CitationTooltipProps) {
  const sourceTargetId =
    `${messageId}-source-`
    + source.sourceId

  const accordionId =
    `${messageId}-sources`

  const tooltipId =
    `${sourceTargetId}-tooltip`

  const snippet =
    source.snippet?.trim()
    || (
      "A text preview is not "
      + "available for this older "
      + "saved response."
    )

  const openSourceDetails =
    () => {
      const accordion =
        document.getElementById(
          accordionId,
        )

      if (
        accordion
        instanceof HTMLDetailsElement
      ) {
        accordion.open = true
      }

      window.requestAnimationFrame(
        () => {
          document
            .getElementById(
              sourceTargetId,
            )
            ?.scrollIntoView({
              behavior: "smooth",
              block: "center",
            })
        },
      )
    }

  return (
    <span className="group relative inline-flex align-baseline">
      <a
        data-tour="inline-citation"
        href={`#${sourceTargetId}`}
        aria-describedby={tooltipId}
        className="mx-0.5 inline-flex min-w-6 items-center justify-center rounded-md border border-primary/20 bg-accent px-1.5 py-0.5 text-[11px] font-semibold leading-none text-primary no-underline transition hover:border-primary/45 hover:bg-accent/80 focus:outline-none focus:ring-2 focus:ring-primary/30"
        onClick={(event) => {
          event.preventDefault()
          openSourceDetails()
        }}
      >
        [{source.sourceId}]
      </a>

      <span
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none invisible absolute left-0 top-[calc(100%+0.55rem)] z-50 w-[min(21rem,calc(100vw-2rem))] rounded-xl border border-border/70 bg-popover/98 p-3 text-left text-popover-foreground opacity-0 shadow-2xl backdrop-blur-xl transition group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
      >
        <span className="block text-xs font-semibold">
          Source {source.sourceId}
        </span>

        <span className="mt-1 block text-[11px] font-medium leading-5">
          {source.sectionTitle}
        </span>

        <span className="mt-1 block text-[10px] text-muted-foreground">
          {formatPages(source)}
        </span>

        <span className="mt-2 block max-h-40 overflow-hidden border-t pt-2 text-[11px] leading-5 text-muted-foreground">
          {snippet}
        </span>

        <span className="mt-2 block text-[10px] font-medium text-primary">
          Click to open full source details
        </span>

        <span
          aria-hidden="true"
          className="absolute bottom-full left-3 size-3 translate-y-1/2 rotate-45 border-l border-t bg-popover"
        />
      </span>
    </span>
  )
}
