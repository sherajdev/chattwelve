"use client"

import type React from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useState } from "react"

interface PromptEditorProps {
  initialName?: string
  initialContent?: string
  onSave: (name: string, content: string) => void
  onCancel?: () => void
}

export function PromptEditor({ initialName = "", initialContent = "", onSave, onCancel }: PromptEditorProps) {
  const [name, setName] = useState(initialName)
  const [content, setContent] = useState(initialContent)
  const [errors, setErrors] = useState({ name: "", content: "" })

  const validate = () => {
    const newErrors = { name: "", content: "" }
    let isValid = true

    if (!name.trim()) {
      newErrors.name = "Prompt name is required"
      isValid = false
    } else if (name.length < 3) {
      newErrors.name = "Name must be at least 3 characters"
      isValid = false
    }

    if (!content.trim()) {
      newErrors.content = "Prompt content is required"
      isValid = false
    } else if (content.length < 10) {
      newErrors.content = "Content must be at least 10 characters"
      isValid = false
    }

    setErrors(newErrors)
    return isValid
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (validate()) {
      onSave(name.trim(), content.trim())
      setName("")
      setContent("")
      setErrors({ name: "", content: "" })
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="prompt-name">Prompt Name</Label>
        <Input
          id="prompt-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., Trading Expert, Market Analyst"
          className={errors.name ? "border-destructive" : ""}
        />
        {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="prompt-content">Prompt Content</Label>
        <Textarea
          id="prompt-content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Enter your system prompt here..."
          className={`min-h-[200px] max-h-[40vh] overflow-y-auto ${errors.content ? "border-destructive" : ""}`}
        />
        {errors.content && <p className="text-xs text-destructive">{errors.content}</p>}
        <p className="text-xs text-muted-foreground">{content.length} characters</p>
      </div>

      <div className="flex gap-2">
        <Button type="submit" className="flex-1 bg-gold text-gold-foreground hover:bg-gold/90">
          Save Prompt
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
