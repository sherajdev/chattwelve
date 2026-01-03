"use client"

import { Edit2, Trash2, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { SystemPrompt } from "@/lib/types"
import { useState } from "react"
import { PromptEditor } from "./prompt-editor"

interface PromptCardProps {
  prompt: SystemPrompt
  isActive: boolean
  onActivate: (id: string) => void
  onDeactivate: () => void
  onDelete: (id: string) => void
  onUpdate: (id: string, name: string, content: string) => void
}

export function PromptCard({ prompt, isActive, onActivate, onDeactivate, onDelete, onUpdate }: PromptCardProps) {
  const [isEditing, setIsEditing] = useState(false)

  const handleSave = (name: string, content: string) => {
    onUpdate(prompt.id, name, content)
    setIsEditing(false)
  }

  if (isEditing) {
    return (
      <PromptEditor
        initialName={prompt.name}
        initialContent={prompt.content}
        onSave={handleSave}
        onCancel={() => setIsEditing(false)}
      />
    )
  }

  return (
    <Card className="relative">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base">{prompt.name}</CardTitle>
            <CardDescription className="text-xs">
              Updated {new Date(prompt.updatedAt).toLocaleDateString()}
            </CardDescription>
          </div>
          {isActive && (
            <Badge className="bg-gold text-gold-foreground">
              <Check className="mr-1 h-3 w-3" />
              Active
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground line-clamp-3">{prompt.content}</p>

        <div className="flex gap-2">
          {!isActive ? (
            <Button size="sm" variant="outline" onClick={() => onActivate(prompt.id)} className="flex-1">
              Activate
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={onDeactivate} className="flex-1 bg-transparent">
              Deactivate
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => setIsEditing(true)}>
            <Edit2 className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onDelete(prompt.id)}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
