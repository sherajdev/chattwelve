/**
 * Next.js middleware for route protection
 * Protects routes that require authentication
 * 
 * Uses cookie-based session checking (Edge-compatible)
 * The actual session validation happens server-side via BetterAuth API routes
 */

import { NextRequest, NextResponse } from "next/server"

// Routes that require authentication (Option A: chat requires login)
const protectedRoutes = ["/", "/settings", "/chat"]

// Routes only for non-authenticated users
const authRoutes = ["/login", "/signup"]

// BetterAuth session cookie name (default)
const SESSION_COOKIE_NAME = "better-auth.session_token"

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Check for session cookie (BetterAuth stores session in cookies)
  const sessionCookie = request.cookies.get(SESSION_COOKIE_NAME)
  const hasSession = !!sessionCookie?.value

  // Check if accessing a protected route without session
  const isProtectedRoute = protectedRoutes.some(
    (route) => pathname === route || (route !== "/" && pathname.startsWith(route))
  )

  if (isProtectedRoute && !hasSession) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("callbackUrl", pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Check if accessing auth routes with session (redirect to home)
  const isAuthRoute = authRoutes.some((route) => pathname.startsWith(route))

  if (isAuthRoute && hasSession) {
    return NextResponse.redirect(new URL("/", request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - api/auth (auth endpoints handled by BetterAuth)
     * - _next (Next.js internals)
     * - static files (images, fonts, etc.)
     */
    "/((?!api/auth|_next/static|_next/image|favicon.ico|.*\\.png$|.*\\.jpg$|.*\\.svg$).*)",
  ],
}
