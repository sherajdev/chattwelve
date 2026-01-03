"use client"

import { Copy, Check } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { Message as MessageType } from "@/lib/types"
import { useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

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

  // Convert epoch timestamps to human-readable format in user's timezone
  const formatEpochTimestamps = (text: string): string => {
    // Match patterns like "epoch 1767445140" or "timestamp 1767445140"
    const epochRegex = /\b(epoch|timestamp)\s+(\d{10,13})\b/gi

    let result = text.replace(epochRegex, (match, label, epochStr) => {
      const epoch = parseInt(epochStr, 10)
      // Handle both seconds (10 digits) and milliseconds (13 digits)
      const timestamp = epochStr.length === 13 ? epoch : epoch * 1000
      const date = new Date(timestamp)

      const formatted = date.toLocaleString(undefined, {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      })

      return formatted
    })

    // Also match standalone 10-digit numbers that look like Unix timestamps (after "at" or similar context)
    const standaloneEpochRegex = /\bat\s+(\d{10})\b/gi
    result = result.replace(standaloneEpochRegex, (match, epochStr) => {
      const epoch = parseInt(epochStr, 10)
      const date = new Date(epoch * 1000)

      // Sanity check: only convert if it's a reasonable date (2020-2030)
      const year = date.getFullYear()
      if (year < 2020 || year > 2030) return match

      const formatted = date.toLocaleString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      })

      return `at ${formatted}`
    })

    return result
  }

  // Process message content for AI messages
  const processedContent = isUser ? message.content : formatEpochTimestamps(message.content)

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
            isUser ? "bg-card text-card-foreground" : "bg-muted/50"
          }`}
        >
          {isUser ? (
            <p className="text-sm leading-relaxed">{message.content}</p>
          ) : (
            <div className="prose prose-sm prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Headers
                  h1: ({ children }) => (
                    <h1 className="text-xl font-bold text-foreground mt-4 mb-2 first:mt-0">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-lg font-semibold text-foreground mt-4 mb-2 first:mt-0 border-b border-border/50 pb-1">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-base font-semibold text-foreground mt-3 mb-1">{children}</h3>
                  ),
                  // Paragraphs
                  p: ({ children }) => (
                    <p className="text-sm text-foreground/90 leading-relaxed my-2">{children}</p>
                  ),
                  // Lists
                  ul: ({ children }) => (
                    <ul className="list-disc list-outside ml-4 my-2 space-y-1">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-outside ml-4 my-2 space-y-1">{children}</ol>
                  ),
                  li: ({ children }) => (
                    <li className="text-sm text-foreground/90">{children}</li>
                  ),
                  // Bold & Strong - highlight financial data in gold
                  strong: ({ children }) => {
                    const text = String(children)
                    const isFinancial = /^\$[\d,]+\.?\d*$|^[+-]?\d+\.?\d*%$/.test(text)
                    return (
                      <strong className={isFinancial ? "text-gold font-semibold" : "text-foreground font-semibold"}>
                        {children}
                      </strong>
                    )
                  },
                  // Italic
                  em: ({ children }) => (
                    <em className="text-muted-foreground italic">{children}</em>
                  ),
                  // Links
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gold hover:text-gold/80 underline underline-offset-2 transition-colors"
                    >
                      {children}
                    </a>
                  ),
                  // Code (inline)
                  code: ({ children, className }) => {
                    const isBlock = className?.includes("language-")
                    if (isBlock) {
                      return (
                        <code className="block bg-background/50 rounded-md p-3 my-2 text-xs font-mono overflow-x-auto">
                          {children}
                        </code>
                      )
                    }
                    return (
                      <code className="bg-background/50 px-1.5 py-0.5 rounded text-xs font-mono text-gold">
                        {children}
                      </code>
                    )
                  },
                  // Blockquote
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-gold/50 pl-3 my-2 italic text-muted-foreground">
                      {children}
                    </blockquote>
                  ),
                  // Horizontal rule
                  hr: () => <hr className="border-border/50 my-4" />,
                  // Tables
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-2">
                      <table className="min-w-full text-sm border border-border/50 rounded">{children}</table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-background/50">{children}</thead>
                  ),
                  th: ({ children }) => (
                    <th className="px-3 py-2 text-left font-semibold text-foreground border-b border-border/50">{children}</th>
                  ),
                  td: ({ children }) => (
                    <td className="px-3 py-2 text-foreground/90 border-b border-border/30">{children}</td>
                  ),
                }}
              >
                {processedContent}
              </ReactMarkdown>
            </div>
          )}
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
