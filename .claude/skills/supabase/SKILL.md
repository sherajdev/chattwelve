# Supabase Skill for ChatTwelve

## Overview

Supabase provides PostgreSQL database and real-time subscriptions for ChatTwelve.

**Important:** ChatTwelve uses **BetterAuth for authentication**, NOT Supabase Auth. Supabase is used purely as:
- PostgreSQL database (same database BetterAuth connects to)
- Real-time subscriptions for live chat updates
- File storage (optional, for user avatars)

This means `auth.uid()` and Supabase Auth functions are NOT available. All database operations requiring user context go through the FastAPI backend using the service role key.

## Installation

```bash
cd frontend
npm install @supabase/supabase-js @supabase/ssr
```

## Client Setup

### Server Client (frontend/lib/supabase/server.ts)

For Server Components, Route Handlers, and Server Actions:

```typescript
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { Database } from "./types";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // Called from Server Component, cookies are read-only
          }
        },
      },
    }
  );
}
```

### Browser Client (frontend/lib/supabase/client.ts)

For Client Components:

```typescript
import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "./types";

export function createClient() {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

### Note on Middleware

**Do NOT use Supabase middleware for authentication.** ChatTwelve uses BetterAuth for auth.

The Supabase client in the frontend is only used for:
- Real-time subscriptions (listening to database changes)
- Direct queries that don't require user context

All user-authenticated operations go through the FastAPI backend, which:
1. Validates the BetterAuth session
2. Uses the Supabase service role key to query the database
3. Filters results by user_id

## Type Generation

Generate TypeScript types from your Supabase schema:

```bash
# Install Supabase CLI
npm install -g supabase

# Login
supabase login

# Generate types
supabase gen types typescript \
  --project-id YOUR_PROJECT_ID \
  --schema public \
  > frontend/lib/supabase/types.ts
```

### Example Generated Types

These types should align with `frontend/lib/types.ts`:

```typescript
// frontend/lib/supabase/types.ts
export type Database = {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;  // BetterAuth user.id (TEXT, not UUID)
          email: string;
          display_name: string | null;
          avatar_url: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id: string;
          email: string;
          display_name?: string | null;
          avatar_url?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          email?: string;
          display_name?: string | null;
          avatar_url?: string | null;
          updated_at?: string;
        };
      };
      chat_sessions: {
        Row: {
          id: string;
          user_id: string;
          title: string;
          created_at: string;
          updated_at: string;
          last_message_at: string;  // Matches frontend ChatSession.lastMessageAt
          request_count: number;     // Rate limiting
          request_window_start: string;
          context: Record<string, unknown>[];  // Backward compat during migration
        };
        Insert: {
          id?: string;
          user_id: string;
          title?: string;
          created_at?: string;
          updated_at?: string;
          last_message_at?: string;
        };
        Update: {
          title?: string;
          updated_at?: string;
          last_message_at?: string;
          request_count?: number;
          request_window_start?: string;
        };
      };
      chat_messages: {
        Row: {
          id: string;
          session_id: string;
          role: "user" | "assistant" | "system";
          content: string;
          model: string | null;  // Matches frontend Message.model
          metadata: Record<string, unknown>;
          created_at: string;
        };
        Insert: {
          id?: string;
          session_id: string;
          role: "user" | "assistant" | "system";
          content: string;
          model?: string | null;
          metadata?: Record<string, unknown>;
          created_at?: string;
        };
        Update: {
          content?: string;
          model?: string | null;
          metadata?: Record<string, unknown>;
        };
      };
    };
  };
};

// Helper types (align with frontend/lib/types.ts)
export type Profile = Database["public"]["Tables"]["profiles"]["Row"];
export type ChatSession = Database["public"]["Tables"]["chat_sessions"]["Row"];
export type ChatMessage = Database["public"]["Tables"]["chat_messages"]["Row"];

// Convenience type matching frontend Message interface
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  model?: string;
};
```

## Common Query Patterns

### Server Component Queries

```typescript
// frontend/app/(protected)/page.tsx
import { createClient } from "@/lib/supabase/server";

export default async function ChatPage() {
  const supabase = await createClient();
  
  // Get current user's sessions
  const { data: sessions, error } = await supabase
    .from("chat_sessions")
    .select("*")
    .order("updated_at", { ascending: false });

  if (error) {
    console.error("Error fetching sessions:", error);
    return <div>Error loading chats</div>;
  }

  return <ChatInterface sessions={sessions} />;
}
```

### Client Component Queries

```typescript
"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { ChatMessage } from "@/lib/supabase/types";

export function ChatMessages({ sessionId }: { sessionId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const supabase = createClient();

  useEffect(() => {
    async function fetchMessages() {
      const { data, error } = await supabase
        .from("chat_messages")
        .select("*")
        .eq("session_id", sessionId)
        .order("created_at", { ascending: true });

      if (!error && data) {
        setMessages(data);
      }
      setIsLoading(false);
    }

    fetchMessages();
  }, [sessionId]);

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      {messages.map((msg) => (
        <div key={msg.id}>{msg.content}</div>
      ))}
    </div>
  );
}
```

### Insert Operations

```typescript
// Create a new chat session
const { data: session, error } = await supabase
  .from("chat_sessions")
  .insert({
    user_id: userId,
    title: "New Chat",
  })
  .select()
  .single();

// Add a message
const { error } = await supabase
  .from("chat_messages")
  .insert({
    session_id: sessionId,
    role: "user",
    content: messageContent,
  });
```

### Update Operations

```typescript
// Update session title
const { error } = await supabase
  .from("chat_sessions")
  .update({ 
    title: newTitle,
    updated_at: new Date().toISOString(),
  })
  .eq("id", sessionId);
```

### Delete Operations

```typescript
// Delete a session (messages cascade)
const { error } = await supabase
  .from("chat_sessions")
  .delete()
  .eq("id", sessionId);
```

## Real-time Subscriptions

### Subscribe to New Messages

```typescript
"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { ChatMessage } from "@/lib/supabase/types";

export function useChatSubscription(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const supabase = createClient();

  useEffect(() => {
    // Initial fetch
    supabase
      .from("chat_messages")
      .select("*")
      .eq("session_id", sessionId)
      .order("created_at", { ascending: true })
      .then(({ data }) => {
        if (data) setMessages(data);
      });

    // Subscribe to changes
    const channel = supabase
      .channel(`messages:${sessionId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "chat_messages",
          filter: `session_id=eq.${sessionId}`,
        },
        (payload) => {
          setMessages((prev) => [...prev, payload.new as ChatMessage]);
        }
      )
      .on(
        "postgres_changes",
        {
          event: "DELETE",
          schema: "public",
          table: "chat_messages",
          filter: `session_id=eq.${sessionId}`,
        },
        (payload) => {
          setMessages((prev) => 
            prev.filter((msg) => msg.id !== payload.old.id)
          );
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [sessionId]);

  return messages;
}
```

## Row Level Security (RLS)

### Important: BetterAuth + RLS

Since ChatTwelve uses BetterAuth (not Supabase Auth), the `auth.uid()` function is NOT available. Instead:

1. **Backend uses service role key** - bypasses RLS, full access
2. **Frontend anon key has NO access** - all operations go through backend
3. **Backend validates user via BetterAuth** - then queries with user_id filter

### Enable RLS

```sql
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_prompts ENABLE ROW LEVEL SECURITY;
```

### Policy Configuration (Service Role Approach)

```sql
-- Service role has full access (backend uses this)
CREATE POLICY "Service role full access"
  ON public.profiles FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role full access"
  ON public.chat_sessions FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role full access"
  ON public.chat_messages FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role full access"
  ON public.system_prompts FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Anon key: only allow real-time subscriptions (SELECT on messages)
-- This enables frontend real-time without exposing write access
CREATE POLICY "Anon can subscribe to messages"
  ON public.chat_messages FOR SELECT
  TO anon
  USING (true);  -- Further filtering done by subscription filter
```

### Backend Authorization Pattern

Since we can't use `auth.uid()`, implement authorization in FastAPI:

```python
# src/routers/chat.py
from src.services.auth import get_current_user

@router.get("/sessions")
async def get_sessions(user: User = Depends(get_current_user)):
    # user.id comes from BetterAuth session validation
    supabase = get_supabase_client()  # Uses service role

    result = supabase.table("chat_sessions") \
        .select("*") \
        .eq("user_id", user.id) \
        .execute()

    return result.data
```

## Environment Variables

```env
# Frontend (.env.local)
# Supabase client for real-time subscriptions
NEXT_PUBLIC_SUPABASE_URL=https://[project-ref].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...

# BetterAuth uses direct PostgreSQL connection (same database)
DATABASE_URL=postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres
BETTER_AUTH_SECRET=your-secret-min-32-chars
BETTER_AUTH_URL=http://localhost:3000
NEXT_PUBLIC_APP_URL=http://localhost:3000

# Backend (.env)
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # Bypasses RLS - keep secret!
```

**Note:** Both BetterAuth and Supabase connect to the same PostgreSQL database:
- BetterAuth: Direct connection via `DATABASE_URL`
- Supabase: REST API via `SUPABASE_URL` + keys

## Backend Integration (Python)

```python
# src/core/supabase.py
import os
from supabase import create_client, Client

_supabase_client: Client | None = None

def get_supabase() -> Client:
    """Get Supabase client with service role (bypasses RLS)."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        )
    return _supabase_client

# Usage in services
async def create_chat_session(user_id: str, title: str = "New Chat"):
    """Create session for authenticated user (user_id from BetterAuth)."""
    supabase = get_supabase()
    result = supabase.table("chat_sessions").insert({
        "user_id": user_id,
        "title": title
    }).execute()
    return result.data[0]

async def add_message(session_id: str, role: str, content: str, model: str = None):
    """Add message to session, optionally with model info."""
    supabase = get_supabase()
    result = supabase.table("chat_messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "model": model  # Track which AI model generated response
    }).execute()

    # Update session's last_message_at
    supabase.table("chat_sessions").update({
        "last_message_at": "now()"
    }).eq("id", session_id).execute()

    return result.data[0]
```

## Common Issues

### 1. RLS blocking queries
- **With BetterAuth:** Use service role key in backend (bypasses RLS)
- Ensure backend validates user via BetterAuth before querying
- Frontend should NOT make direct Supabase queries for user data

### 2. Real-time not working
- Enable replication for the table in Supabase dashboard (Database → Replication)
- Ensure anon key has SELECT policy on the table
- Verify channel subscription filter matches your query
- Check browser console for WebSocket errors

### 3. Type mismatches
- Regenerate types after schema changes: `supabase gen types typescript`
- Ensure types align with `frontend/lib/types.ts`
- Check that `model` field exists in `chat_messages` table

### 4. BetterAuth user not in profiles table
- Create profile when user signs up via BetterAuth callback:
```typescript
// In BetterAuth config
callbacks: {
  async onUserCreated({ user }) {
    await supabase.table('profiles').insert({
      id: user.id,
      email: user.email,
      display_name: user.name,
    });
  }
}
```

### 5. Database connection issues
- Verify `DATABASE_URL` format for BetterAuth (direct PostgreSQL)
- Verify `SUPABASE_URL` format for Supabase client (REST API)
- Check Supabase dashboard for connection pool limits
