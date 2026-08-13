import {
  Bot,
} from "lucide-react"

import {
  Avatar,
  AvatarFallback,
} from "@/components/ui/avatar"

interface ThinkingIndicatorProps {
  label: string
}

export function ThinkingIndicator({
  label,
}: ThinkingIndicatorProps) {
  return (
    <div
      className="flex gap-3"
      role="status"
      aria-live="polite"
    >
      <Avatar className="mt-0.5 size-9 border">
        <AvatarFallback className="bg-muted">
          <Bot
            className="size-4"
            aria-hidden="true"
          />
        </AvatarFallback>
      </Avatar>

      <div className="space-y-2 rounded-2xl rounded-tl-md border bg-card px-4 py-3 shadow-sm">
        <p className="text-xs text-muted-foreground">
          {label}
        </p>

        <div className="flex items-center gap-1">
          {[0, 1, 2].map(
            (index) => (
              <span
                key={index}
                className="size-2 animate-bounce rounded-full bg-muted-foreground/60"
                style={{
                  animationDelay:
                    `${index * 120}ms`,
                }}
              />
            ),
          )}
        </div>
      </div>
    </div>
  )
}
