# BetterAuth Skill for ChatTwelve

## Overview
BetterAuth is a framework-agnostic authentication library. This skill covers integration with Next.js 16 and Supabase PostgreSQL.

## Installation

```bash
cd frontend
npm install better-auth pg
```

## Core Configuration

### Server Setup (frontend/lib/auth.ts)

```typescript
import { betterAuth } from "better-auth";
import { Pool } from "pg";

export const auth = betterAuth({
  // Use Supabase PostgreSQL
  database: new Pool({
    connectionString: process.env.DATABASE_URL,
  }),
  
  // Email/Password auth
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: false, // Enable in production
    sendResetPassword: async ({ user, url }) => {
      // Integrate with email service (Resend, SendGrid, etc.)
      console.log(`Reset password for ${user.email}: ${url}`);
    },
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
  
  // OAuth providers (optional)
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    },
    github: {
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    },
  },

  // Callbacks
  callbacks: {
    session: async ({ session, user }) => {
      // Add custom fields to session
      return {
        ...session,
        user: {
          ...session.user,
          id: user.id,
        },
      };
    },
  },
});

// Export types
export type Session = typeof auth.$Infer.Session;
export type User = typeof auth.$Infer.User;
```

### Client Setup (frontend/lib/auth-client.ts)

```typescript
import { createAuthClient } from "better-auth/react";

const authClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000",
});

export const {
  signIn,
  signUp,
  signOut,
  useSession,
  getSession,
} = authClient;
```

## API Route Handler

### Catch-all Route (frontend/app/api/auth/[...all]/route.ts)

```typescript
import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const { GET, POST } = toNextJsHandler(auth);
```

## Middleware Protection

### Route Protection (frontend/middleware.ts)

**Note:** The `"/"` route protection is optional. Remove it from `protectedRoutes` if you want to allow guest access to the main chat interface.

```typescript
import { auth } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

// Routes that require authentication
// NOTE: Remove "/" if guest access to chat is allowed
const protectedRoutes = ["/settings", "/chat"];
// Routes only for non-authenticated users
const authRoutes = ["/login", "/signup"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  const session = await auth.api.getSession({
    headers: request.headers,
  });

  // Redirect to login if accessing protected route without session
  if (protectedRoutes.some(route => pathname.startsWith(route)) && !session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Redirect to home if accessing auth routes with session
  if (authRoutes.some(route => pathname.startsWith(route)) && session) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - api/auth (auth endpoints)
     * - _next (Next.js internals)
     * - static files
     */
    "/((?!api/auth|_next/static|_next/image|favicon.ico).*)",
  ],
};
```

## React Components

### Auth Provider (frontend/components/auth/auth-provider.tsx)

```typescript
"use client";

import { createContext, useContext, ReactNode } from "react";
import { useSession } from "@/lib/auth-client";
import type { Session } from "@/lib/auth";

interface AuthContextType {
  session: Session | null;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({
  session: null,
  isLoading: true,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: session, isPending } = useSession();

  return (
    <AuthContext.Provider value={{ session, isLoading: isPending }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
```

### Login Form (frontend/components/auth/login-form.tsx)

```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";

export function LoginForm() {
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setIsLoading(true);

    const formData = new FormData(e.currentTarget);
    const email = formData.get("email") as string;
    const password = formData.get("password") as string;

    try {
      const result = await signIn.email({ email, password });

      if (result.error) {
        toast({
          title: "Login failed",
          description: result.error.message,
        });
      } else {
        router.push("/");
        router.refresh();
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Something went wrong. Please try again.",
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Welcome back</CardTitle>
        <CardDescription>Sign in to your ChatTwelve account</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="you@example.com"
              required
              disabled={isLoading}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              required
              disabled={isLoading}
            />
          </div>
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Sign in
          </Button>
        </form>

        {/* OAuth buttons */}
        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-background px-2 text-muted-foreground">
              Or continue with
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Button
            variant="outline"
            onClick={() => signIn.social({ provider: "google" })}
            disabled={isLoading}
          >
            Google
          </Button>
          <Button
            variant="outline"
            onClick={() => signIn.social({ provider: "github" })}
            disabled={isLoading}
          >
            GitHub
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

### Signup Form (frontend/components/auth/signup-form.tsx)

```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signUp } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";

export function SignupForm() {
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setIsLoading(true);

    const formData = new FormData(e.currentTarget);
    const name = formData.get("name") as string;
    const email = formData.get("email") as string;
    const password = formData.get("password") as string;

    try {
      const result = await signUp.email({ name, email, password });

      if (result.error) {
        toast({
          title: "Signup failed",
          description: result.error.message,
        });
      } else {
        toast({
          title: "Account created",
          description: "Welcome to ChatTwelve!",
        });
        router.push("/");
        router.refresh();
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Something went wrong. Please try again.",
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Create an account</CardTitle>
        <CardDescription>Get started with ChatTwelve</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              name="name"
              placeholder="Your name"
              required
              disabled={isLoading}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="you@example.com"
              required
              disabled={isLoading}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              minLength={8}
              required
              disabled={isLoading}
            />
          </div>
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create account
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

## Server-Side Session Access

```typescript
// In Server Components or Route Handlers
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

export default async function Page() {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session) {
    redirect("/login");
  }

  return <div>Welcome, {session.user.name}!</div>;
}
```

## Environment Variables

```env
# Required
DATABASE_URL=postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres
BETTER_AUTH_SECRET=generate-a-random-32-char-string
BETTER_AUTH_URL=http://localhost:3000
NEXT_PUBLIC_APP_URL=http://localhost:3000  # Required for auth-client.ts

# OAuth (optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

**Important:** Update `frontend/.env.example` with these variables (without sensitive values).

## Database Tables Created by BetterAuth

BetterAuth automatically creates these tables:
- `user` - User accounts
- `session` - Active sessions
- `account` - OAuth account links
- `verification` - Email verification tokens

## Database Setup

Run the BetterAuth CLI to create/migrate database tables:

```bash
cd frontend
npx @better-auth/cli migrate
```

Alternatively, BetterAuth can auto-create tables on first run if the database user has CREATE TABLE permissions.

## Layout Setup

Add the `Toaster` component to your root layout for toast notifications to work:

```typescript
// frontend/app/layout.tsx
import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/components/auth/auth-provider";

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
        <Toaster />
      </body>
    </html>
  );
}
```

## Common Issues

### 1. Session not persisting
- Ensure `BETTER_AUTH_URL` matches your app URL
- Check cookie settings in production (secure: true, sameSite)

### 2. OAuth redirect issues
- Verify callback URLs in provider console
- Check `BETTER_AUTH_URL` is correct

### 3. Database connection errors
- Verify `DATABASE_URL` format
- Ensure Supabase allows connections from your IP
