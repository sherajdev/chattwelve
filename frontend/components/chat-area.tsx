"use client"

import { Message } from "./message"
import { TypingIndicator } from "./typing-indicator"
import { EmptyState } from "./empty-state"
import type { Message as MessageType } from "@/lib/types"
import { useEffect, useRef } from "react"

interface ChatAreaProps {
  messages: MessageType[]
  isStreaming: boolean
  onSuggestionClick: (suggestion: string) => void
}

export function ChatArea({ messages, isStreaming, onSuggestionClick }: ChatAreaProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const scrollEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollEndRef.current) {
      scrollEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages, isStreaming])

  return (
    <div
      ref={scrollContainerRef}
      className="flex-1 overflow-y-auto overflow-x-hidden"
    >
      <div className="mx-auto max-w-3xl px-4 py-4">
        {messages.length === 0 ? (
          <EmptyState onSuggestionClick={onSuggestionClick} />
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <Message key={message.id} message={message} />
            ))}
            {isStreaming && <TypingIndicator />}
          </div>
        )}
        <div ref={scrollEndRef} className="h-4" />
      </div>
    </div>
  )
}
