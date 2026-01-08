/**
 * Profile form component
 * Allows users to update their display name and avatar
 */

"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { profileApi, ProfileResponse } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import { Loader2 } from "lucide-react"

interface ProfileFormProps {
  userId: string
  email: string
}

export function ProfileForm({ userId, email }: ProfileFormProps) {
  const [profile, setProfile] = useState<ProfileResponse | null>(null)
  const [displayName, setDisplayName] = useState("")
  const [avatarUrl, setAvatarUrl] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const { toast } = useToast()

  // Load profile
  useEffect(() => {
    const loadProfile = async () => {
      try {
        const data = await profileApi.get(userId)
        setProfile(data)
        setDisplayName(data.display_name || "")
        setAvatarUrl(data.avatar_url || "")
      } catch (error) {
        // Profile might not exist yet - that's ok
        console.log("Profile not found, using defaults")
      } finally {
        setIsLoading(false)
      }
    }

    loadProfile()
  }, [userId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)

    try {
      // Use sync endpoint which creates or updates the profile
      const updated = await profileApi.sync({
        user_id: userId,
        email: email,
        display_name: displayName || null,
        avatar_url: avatarUrl || null,
      })
      setProfile(updated)
      toast({
        title: "Profile updated",
        description: "Your profile has been saved successfully.",
      })
    } catch (error) {
      console.error("Profile save error:", error)
      toast({
        title: "Error",
        description: "Failed to update profile. Please try again.",
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
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border bg-card p-4">
      <div className="space-y-2">
        <Label htmlFor="displayName">Display Name</Label>
        <Input
          id="displayName"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Your display name"
          maxLength={100}
        />
        <p className="text-xs text-muted-foreground">
          This name will be shown in the chat interface.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="avatarUrl">Avatar URL</Label>
        <Input
          id="avatarUrl"
          type="url"
          value={avatarUrl}
          onChange={(e) => setAvatarUrl(e.target.value)}
          placeholder="https://example.com/avatar.png"
        />
        <p className="text-xs text-muted-foreground">
          Link to your profile picture (optional).
        </p>
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={isSaving}>
          {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save Profile
        </Button>
      </div>
    </form>
  )
}
