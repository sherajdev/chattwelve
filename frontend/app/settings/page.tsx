/**
 * Settings page
 * User profile and preferences management
 */

"use client"

import { useAuth } from "@/components/auth/auth-provider"
import { ProfileForm } from "@/components/settings/profile-form"
import { PreferencesForm } from "@/components/settings/preferences-form"
import { Button } from "@/components/ui/button"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"

export default function SettingsPage() {
  const { session, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!session?.user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Please log in to access settings.</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center gap-4 px-4">
          <Link href="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <h1 className="text-xl font-semibold">Settings</h1>
        </div>
      </header>

      {/* Content */}
      <main className="container mx-auto max-w-2xl px-4 py-8">
        <div className="space-y-8">
          {/* Profile Section */}
          <section>
            <h2 className="mb-4 text-lg font-medium">Profile</h2>
            <ProfileForm userId={session.user.id} email={session.user.email} />
          </section>

          {/* Preferences Section */}
          <section>
            <h2 className="mb-4 text-lg font-medium">Preferences</h2>
            <PreferencesForm userId={session.user.id} />
          </section>

          {/* Account Info */}
          <section>
            <h2 className="mb-4 text-lg font-medium">Account</h2>
            <div className="rounded-lg border bg-card p-4">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Email</span>
                  <span>{session.user.email}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">User ID</span>
                  <span className="font-mono text-xs">{session.user.id.slice(0, 8)}...</span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}
