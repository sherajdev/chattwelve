/**
 * BetterAuth client configuration for ChatTwelve
 * Client-side auth utilities for React components
 */

import { createAuthClient } from "better-auth/react"

const authClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000",
})

export const {
  signIn,
  signUp,
  signOut,
  useSession,
  getSession,
} = authClient
