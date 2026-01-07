# Complete Implementation Plan: Local Supabase + BetterAuth

This document outlines the plan for implementing user authentication in ChatTwelve using a self-hosted Supabase instance on Coolify and BetterAuth.

## 📡 Connection Details

| Component | Value |
|-----------|-------|
| **Coolify Server IP** | `192.168.50.253` |
| **Dev Machine IP** | `192.168.50.79` |
| **PostgreSQL Port** | `5432` |
| **PostgreSQL Database** | `postgres` |
| **PostgreSQL User** | `postgres` |
| **Supabase Studio URL** | `http://supabasekong-wco0ck8cg4k8k0sk4k8c8g80.192.168.50.253.sslip.io/project/default` |

---

## 🛠 Phase 1: Dependencies & Environment Configuration

### 1.1 Install Dependencies
```bash
cd frontend && npm install better-auth pg
```

### 1.2 Update Environment Variables
**File**: `frontend/.env.example` (and manually create `frontend/.env.local`)
```env
# Supabase PostgreSQL (BetterAuth database)
DATABASE_URL=postgresql://postgres:[YOUR_PASSWORD]@192.168.50.253:5432/postgres

# BetterAuth Configuration
BETTER_AUTH_SECRET=your-random-32-char-secret-here
BETTER_AUTH_URL=http://localhost:3000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

---

## 🏗 Phase 2: BetterAuth Core Setup

- **frontend/lib/auth.ts**: Server-side configuration with PostgreSQL Pool.
- **frontend/lib/auth-client.ts**: Client-side utilities (`signIn`, `signUp`, `useSession`).
- **frontend/app/api/auth/[...all]/route.ts**: Catch-all API route handler.

---

## 🛡 Phase 3: Route Protection (Option A)

- **frontend/middleware.ts**: Protects `/`, `/settings`, and `/chat`. Redirects guests to `/login`.

---

## 🧩 Phase 4: Auth Components (shadcn/ui style)

- **frontend/components/auth/auth-provider.tsx**: Context provider.
- **frontend/components/auth/login-form.tsx**: Email/Password login.
- **frontend/components/auth/signup-form.tsx**: Registration (Auto-login, no verification).
- **frontend/components/auth/user-menu.tsx**: User dropdown with logout at bottom of sidebar.

---

## 📄 Phase 5: Auth Pages

- **frontend/app/login/page.tsx**: Centered login layout.
- **frontend/app/signup/page.tsx**: Centered signup layout.

---

## 🔌 Phase 6: Integration with Existing System

- **frontend/app/layout.tsx**: Add `AuthProvider` and `Toaster`.
- **frontend/lib/api.ts**: Update `sessionApi.create()` to accept `userId`.
- **frontend/hooks/use-session.ts**: Update `createNewSession()` to pass `userId`.
- **frontend/components/sidebar.tsx**: Add `UserMenu` at the bottom.
- **frontend/app/page.tsx**: Pass `authSession.user.id` when creating new chats.

---

## 🧪 Phase 7: Testing

- **frontend/tests/auth.spec.ts**: Playwright tests for signup, login, and logout flows.

---

## 📝 Implementation Strategy
- **Database Tables**: BetterAuth will auto-create `user`, `session`, `account`, and `verification` tables on first run.
- **Authentication Mode**: Email/Password only.
- **Protection Mode**: Option A (Login required for chat).
