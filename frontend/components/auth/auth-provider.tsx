"use client"

/**
 * Auth Provider component
 * Wraps the application with authentication context
 */

import { createContext, useContext, ReactNode } from "react"
import { useSession } from "@/lib/auth-client"
import type { Session } from "@/lib/auth"

interface AuthContextType {
  session: Session | null
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType>({
  session: null,
  isLoading: true,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: session, isPending } = useSession()

  return (
    <AuthContext.Provider value={{ session: session as Session | null, isLoading: isPending }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
