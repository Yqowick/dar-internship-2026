import {
  BookOpenText,
} from "lucide-react"

export function EmptyChatState() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center px-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-muted">
        <BookOpenText
          className="size-6 text-muted-foreground"
          aria-hidden="true"
        />
      </div>

      <h2 className="mt-4 text-lg font-semibold">
        New CIS Controls chat
      </h2>

      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
        Ask your first question below.
        This conversation will be saved
        automatically in your chat history.
      </p>
    </div>
  )
}
