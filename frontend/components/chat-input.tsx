"use client"

import type React from "react"

import { Send, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useState } from "react"

interface ChatInputProps {
  onSendMessage: (message: string) => void
  onOpenPromptSettings: () => void
  isStreaming: boolean
  hasActivePrompt: boolean
}

export function ChatInput({ onSendMessage, onOpenPromptSettings, isStreaming, hasActivePrompt }: ChatInputProps) {
  const [input, setInput] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !isStreaming) {
      onSendMessage(input.trim())
      setInput("")
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div
      className="border-t border-border bg-background p-4"
      style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
    >
      <form onSubmit={handleSubmit} className="mx-auto max-w-3xl">
        <div className="relative flex items-end gap-2">
          {/* Prompt Settings Button */}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onOpenPromptSettings}
            className="relative mb-2 shrink-0"
            title="Prompt settings"
          >
            <Settings className="h-5 w-5" />
            {hasActivePrompt && (
              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-gold" title="Active prompt" />
            )}
          </Button>

          {/* Input Textarea */}
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about markets, stocks, or trading strategies..."
            className="min-h-[60px] max-h-[200px] resize-none bg-muted pr-12"
            disabled={isStreaming}
          />

          {/* Send Button */}
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isStreaming}
            className="absolute bottom-2 right-2 h-8 w-8 bg-gold text-gold-foreground hover:bg-gold/90"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  )
}
