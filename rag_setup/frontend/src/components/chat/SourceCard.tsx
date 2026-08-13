import { BookOpenText, FileText } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import type { ChatSource } from "@/types/chat"

interface SourceCardProps {
  source: ChatSource
}

function formatPages(source: ChatSource): string {
  if (source.pageNumber === null) {
    return "Page unavailable"
  }

  if (
    source.endPageNumber === null ||
    source.endPageNumber === source.pageNumber
  ) {
    return `Page ${source.pageNumber}`
  }

  return `Pages ${source.pageNumber}–${source.endPageNumber}`
}

export function SourceCard({ source }: SourceCardProps) {
  return (
    <Card className="gap-0 border-border/70 bg-muted/30 py-0 shadow-none">
      <CardContent className="space-y-2 p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-2">
            <BookOpenText
              className="mt-0.5 size-4 shrink-0 text-primary"
              aria-hidden="true"
            />
            <p className="line-clamp-2 text-xs font-medium leading-5">
              {source.sectionTitle}
            </p>
          </div>

          <Badge variant="secondary" className="shrink-0 text-[10px]">
            {formatPages(source)}
          </Badge>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <FileText className="size-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">{source.sourceDocument}</span>
        </div>
      </CardContent>
    </Card>
  )
}
