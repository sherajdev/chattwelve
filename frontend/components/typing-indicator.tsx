export function TypingIndicator() {
  return (
    <div className="flex gap-4 px-4 py-6">
      <div className="flex max-w-[80%] flex-col gap-2">
        <div className="rounded-lg bg-muted px-4 py-3">
          <div className="flex items-center gap-1">
            <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
            <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
            <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" />
          </div>
        </div>
      </div>
    </div>
  )
}
