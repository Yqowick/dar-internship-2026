import {
  BookOpenText,
  ChevronDown,
  FileText,
  Hash,
  MapPinned,
  Quote,
} from "lucide-react"

import {
  Badge,
} from "@/components/ui/badge"
import type {
  ChatSource,
} from "@/types/chat"

interface SourceMetadataAccordionProps {
  messageId: string
  sources: ChatSource[]
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

export function SourceMetadataAccordion({
  messageId,
  sources,
}: SourceMetadataAccordionProps) {
  const accordionId =
    `${messageId}-sources`

  return (
    <details
      data-tour="source-metadata"
      id={accordionId}
      className="group overflow-hidden rounded-2xl border border-border/70 bg-card/70 shadow-[0_8px_24px_rgba(29,55,83,0.06)] backdrop-blur"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-foreground marker:content-none hover:bg-accent/35">
        <span className="flex items-center gap-2">
          <BookOpenText
            className="size-4 text-primary"
            aria-hidden="true"
          />

          Sources and metadata

          <Badge
            variant="secondary"
            className="h-5 min-w-5 justify-center px-1.5 text-[10px]"
          >
            {sources.length}
          </Badge>
        </span>

        <ChevronDown
          className="size-4 text-muted-foreground transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>

      <div className="space-y-3 border-t p-3">
        {sources.map((source) => {
          const sourceTargetId =
            `${messageId}-source-`
            + source.sourceId

          const snippet =
            source.snippet?.trim()
            || (
              "A source preview is not "
              + "available for this older "
              + "saved response."
            )

          return (
            <article
              id={sourceTargetId}
              key={
                `${source.sourceId}-`
                + source.chunkId
              }
              className="scroll-mt-24 rounded-xl border border-border/70 bg-background/90 p-3 transition target:border-primary target:ring-2 target:ring-primary/20"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-primary">
                    Source {source.sourceId}
                  </p>

                  <h3 className="mt-1 text-xs font-medium leading-5">
                    {source.sectionTitle}
                  </h3>
                </div>

                <Badge
                  variant="outline"
                  className="shrink-0 text-[10px]"
                >
                  {formatPages(source)}
                </Badge>
              </div>

              <dl className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
                <div className="flex min-w-0 items-start gap-2">
                  <FileText
                    className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />

                  <div className="min-w-0">
                    <dt className="font-medium">
                      Document
                    </dt>
                    <dd className="truncate text-muted-foreground">
                      {source.sourceDocument}
                    </dd>
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <MapPinned
                    className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />

                  <div>
                    <dt className="font-medium">
                      Location
                    </dt>
                    <dd className="text-muted-foreground">
                      {formatPages(source)}
                    </dd>
                  </div>
                </div>

                <div className="flex min-w-0 items-start gap-2 sm:col-span-2">
                  <Hash
                    className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />

                  <div className="min-w-0">
                    <dt className="font-medium">
                      Chunk ID
                    </dt>
                    <dd className="break-all font-mono text-[10px] text-muted-foreground">
                      {source.chunkId}
                    </dd>
                  </div>
                </div>
              </dl>

              <div className="mt-3 rounded-lg bg-muted/50 p-3">
                <div className="flex items-center gap-1.5 text-[11px] font-medium">
                  <Quote
                    className="size-3.5 text-primary"
                    aria-hidden="true"
                  />
                  Retrieved snippet
                </div>

                <p className="mt-1.5 text-[11px] leading-5 text-muted-foreground">
                  {snippet}
                </p>
              </div>
            </article>
          )
        })}
      </div>
    </details>
  )
}
