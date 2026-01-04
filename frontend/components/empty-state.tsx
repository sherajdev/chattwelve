"use client"

import { Button } from "@/components/ui/button"
import Image from "next/image"

interface EmptyStateProps {
  onSuggestionClick: (suggestion: string) => void
}

export function EmptyState({ onSuggestionClick }: EmptyStateProps) {
  const suggestions = [
    "What's the current price of gold?",
    "Give me the latest Bitcoin news",
    "EUR/USD exchange rate analysis",
    "AAPL stock performance today",
  ]

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4">
      {/* Logo */}
      <div className="mb-6">
        <Image
          src="/logo.png"
          alt="ChatTwelve Logo"
          width={80}
          height={80}
          className="rounded-2xl"
        />
      </div>

      {/* Tagline */}
      <h2 className="mb-2 text-2xl font-semibold text-balance text-center">Welcome to ChatTwelve</h2>
      <p className="mb-8 text-muted-foreground text-pretty text-center">
        Your AI-powered trading assistant with real-time market insights
      </p>

      {/* Suggestion Chips */}
      <div className="flex flex-wrap justify-center gap-2">
        {suggestions.map((suggestion, index) => (
          <Button
            key={index}
            variant="outline"
            size="sm"
            onClick={() => onSuggestionClick(suggestion)}
            className="text-sm hover:bg-sidebar-accent"
          >
            {suggestion}
          </Button>
        ))}
      </div>
    </div>
  )
}
