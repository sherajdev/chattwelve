/**
 * Preferences form component
 * Allows users to update their app preferences
 */

"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { profileApi, ProfileResponse, promptsApi, PromptResponse } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import { Loader2 } from "lucide-react"

interface PreferencesFormProps {
  userId: string
}

interface Preferences {
  theme?: "light" | "dark" | "system"
  defaultPromptId?: string
  streamingEnabled?: boolean
  soundEnabled?: boolean
}

export function PreferencesForm({ userId }: PreferencesFormProps) {
  const [preferences, setPreferences] = useState<Preferences>({
    theme: "system",
    streamingEnabled: true,
    soundEnabled: false,
  })
  const [prompts, setPrompts] = useState<PromptResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const { toast } = useToast()

  // Load profile and prompts
  useEffect(() => {
    const loadData = async () => {
      try {
        const [profileData, promptsData] = await Promise.all([
          profileApi.get(userId).catch(() => null),
          promptsApi.list(userId).catch(() => ({ prompts: [], count: 0 })),
        ])

        if (profileData?.preferences) {
          setPreferences({
            theme: (profileData.preferences.theme as Preferences["theme"]) || "system",
            defaultPromptId: profileData.preferences.defaultPromptId as string | undefined,
            streamingEnabled: profileData.preferences.streamingEnabled !== false,
            soundEnabled: !!profileData.preferences.soundEnabled,
          })
        }

        setPrompts(promptsData.prompts)
      } catch (error) {
        console.error("Failed to load preferences:", error)
      } finally {
        setIsLoading(false)
      }
    }

    loadData()
  }, [userId])

  const handleSave = async () => {
    setIsSaving(true)

    try {
      await profileApi.updatePreferences(userId, preferences as Record<string, unknown>)
      toast({
        title: "Preferences saved",
        description: "Your preferences have been updated.",
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save preferences. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center rounded-lg border bg-card p-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4 rounded-lg border bg-card p-4">
      {/* Theme */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Theme</Label>
          <p className="text-xs text-muted-foreground">Choose your preferred color theme.</p>
        </div>
        <Select
          value={preferences.theme}
          onValueChange={(value: Preferences["theme"]) =>
            setPreferences({ ...preferences, theme: value })
          }
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Select theme" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="system">System</SelectItem>
            <SelectItem value="light">Light</SelectItem>
            <SelectItem value="dark">Dark</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Default Prompt */}
      {prompts.length > 0 && (
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Default System Prompt</Label>
            <p className="text-xs text-muted-foreground">
              AI personality for new conversations.
            </p>
          </div>
          <Select
            value={preferences.defaultPromptId || "system-default"}
            onValueChange={(value) =>
              setPreferences({ ...preferences, defaultPromptId: value === "system-default" ? undefined : value })
            }
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="System default" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="system-default">System default</SelectItem>
              {prompts.map((prompt) => (
                <SelectItem key={prompt.id} value={prompt.id}>
                  {prompt.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Streaming */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Streaming Responses</Label>
          <p className="text-xs text-muted-foreground">
            Show AI responses as they are generated.
          </p>
        </div>
        <Switch
          checked={preferences.streamingEnabled}
          onCheckedChange={(checked) =>
            setPreferences({ ...preferences, streamingEnabled: checked })
          }
        />
      </div>

      {/* Sound */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Sound Notifications</Label>
          <p className="text-xs text-muted-foreground">
            Play sounds for new messages.
          </p>
        </div>
        <Switch
          checked={preferences.soundEnabled}
          onCheckedChange={(checked) =>
            setPreferences({ ...preferences, soundEnabled: checked })
          }
        />
      </div>

      <div className="flex justify-end pt-2">
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save Preferences
        </Button>
      </div>
    </div>
  )
}
