"use client"

import { Copy, Check } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { Message as MessageType } from "@/lib/types"
import { useState } from "react"

interface MessageProps {
  message: MessageType
}

export function Message({ message }: MessageProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === "user"

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Highlight prices ($X,XXX.XX) and percentages (+/-X.X%) in gold
  const highlightFinancialData = (text: string) => {
    const priceRegex = /\$[\d,]+\.?\d*/g
    const percentageRegex = /[+-]?\d+\.?\d*%/g

    let result = text
    // Replace prices
    result = result.replace(priceRegex, (match) => `<span class="text-gold font-semibold">${match}</span>`)
    // Replace percentages
    result = result.replace(percentageRegex, (match) => `<span class="text-gold font-semibold">${match}</span>`)

    return result
  }

  return (
    <div className={`flex gap-4 px-4 py-6 ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`flex max-w-[80%] flex-col gap-2 ${isUser ? "items-end" : "items-start"}`}>
        {/* AI Model Badge */}
        {!isUser && message.model && (
          <Badge variant="outline" className="text-xs">
            {message.model}
          </Badge>
        )}

        {/* Message Content */}
        <div
          className={`rounded-lg px-4 py-3 ${
            isUser ? "bg-card text-card-foreground" : "bg-muted text-muted-foreground"
          }`}
        >
          <div
            className="whitespace-pre-wrap break-words text-sm leading-relaxed"
            dangerouslySetInnerHTML={{
              __html: !isUser ? highlightFinancialData(message.content) : message.content,
            }}
          />
        </div>

        {/* Copy Button for AI Messages */}
        {!isUser && (
          <Button variant="ghost" size="icon" onClick={handleCopy} className="h-7 w-7" title="Copy message">
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          </Button>
        )}
      </div>
    </div>
  )
}
