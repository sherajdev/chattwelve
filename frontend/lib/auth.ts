/**
 * BetterAuth server configuration for ChatTwelve
 * Uses self-hosted Supabase PostgreSQL as database
 */

import { betterAuth } from "better-auth"
import { Pool } from "pg"

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
