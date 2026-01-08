/**
 * BetterAuth server configuration for ChatTwelve
 * Uses self-hosted Supabase PostgreSQL as database
 */

import { betterAuth } from "better-auth"
import { Pool } from "pg"

// Backend API URL for profile sync
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

/**
 * Sync user profile with backend PostgreSQL
 * Creates/updates profile when user signs up or logs in
 */
async function syncUserProfile(user: { id: string; email: string; name?: string | null; image?: string | null }) {
  try {
    const response = await fetch(`${API_URL}/api/profile/sync`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: user.id,
        email: user.email,
        display_name: user.name || null,
        avatar_url: user.image || null,
      }),
    })

    if (!response.ok) {
      console.error(`Failed to sync profile: ${response.status} ${response.statusText}`)
    }
  } catch (error) {
    // Log but don't fail auth - profile sync is not critical
    console.error("Profile sync error:", error)
  }
}

export const auth = betterAuth({
  // Use Supabase PostgreSQL
  database: new Pool({
    connectionString: process.env.DATABASE_URL,
  }),

  // Email/Password authentication
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: false, // Disabled for development
    minPasswordLength: 8,
  },

  // Session configuration
  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 days
    updateAge: 60 * 60 * 24, // Refresh daily
    cookieCache: {
      enabled: true,
      maxAge: 60 * 5, // 5 minute cache
    },
  },

  // Callbacks
  callbacks: {
    session: async ({ session, user }) => {
      // Sync profile on session creation/update
      await syncUserProfile({
        id: user.id,
        email: user.email,
        name: user.name,
        image: user.image,
      })

      // Add user id to session
      return {
        ...session,
        user: {
          ...session.user,
          id: user.id,
        },
      }
    },
  },
})

// Export types for use in components
export type Session = typeof auth.$Infer.Session
export type User = typeof auth.$Infer.Session.user
