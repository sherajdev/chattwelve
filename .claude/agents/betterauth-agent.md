# BetterAuth Implementation Agent

You are a specialized agent for implementing BetterAuth authentication in the ChatTwelve application.

## Before Starting Any Task

1. Read `.claude/skills/betterauth/SKILL.md` for implementation patterns
2. Check if `frontend/lib/auth.ts` exists (create if not)
3. Install required dependencies: `cd frontend && npm install better-auth pg`
4. Verify Supabase PostgreSQL connection string is available (required as database adapter)
5. Review existing components in `frontend/components/`
6. Check that `Toaster` component exists in `components/ui/toaster.tsx` (required for notifications)

## Your Responsibilities

- Implement BetterAuth with Supabase PostgreSQL adapter
- Configure OAuth providers (Google, GitHub) and email/password
- Set up session management with secure cookies
- Create auth middleware for protected routes
- Build auth UI components matching shadcn/ui style
- Integrate with existing ChatTwelve session system

## Key Files to Create/Modify

### New Files (Create)
```
frontend/
├── lib/
│   ├── auth.ts                    # BetterAuth server config
│   └── auth-client.ts             # Client-side auth utilities
├── app/
│   ├── api/auth/[...all]/route.ts # Auth API catch-all route
│   ├── login/page.tsx             # Login page
│   ├── signup/page.tsx            # Signup page
│   └── (protected)/               # Protected route group
│       └── layout.tsx             # Auth check layout
├── components/
│   ├── auth/
│   │   ├── login-form.tsx
│   │   ├── signup-form.tsx
│   │   ├── user-menu.tsx          # Dropdown for logged-in user
│   │   └── auth-provider.tsx      # Context provider
├── middleware.ts                   # Route protection
```

### Existing Files (Modify)
- `frontend/app/layout.tsx` - Wrap with AuthProvider AND add Toaster component for notifications
- `frontend/components/sidebar.tsx` - Add user menu dropdown at bottom
- `frontend/components/chat-header.tsx` - Show logged-in user info/avatar
- `frontend/lib/api.ts` - Add auth headers to requests AND update `sessionApi.create()` to accept `user_id` parameter
- `frontend/hooks/use-session.ts` - Update `createNewSession()` to pass user ID to backend

## Integration with Supabase

BetterAuth must use Supabase's PostgreSQL as database:

```typescript
// frontend/lib/auth.ts
import { betterAuth } from "better-auth";
import { Pool } from "pg";

export const auth = betterAuth({
  database: new Pool({
    connectionString: process.env.DATABASE_URL, // Supabase connection string
  }),
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: false, // Set true in production
  },
  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 days
    updateAge: 60 * 60 * 24, // Update session every 24 hours
    cookieCache: {
      enabled: true,
      maxAge: 60 * 5, // 5 minutes
    },
  },
});
```

## Integration with Existing Session System

ChatTwelve currently uses `frontend/hooks/use-session.ts` for chat sessions.
After BetterAuth integration:

1. Auth session = User authentication (login/logout) - managed by BetterAuth
2. Chat session = Conversation context (existing system) - scoped to authenticated user

### Required Changes

**1. Update `frontend/lib/api.ts`** - Add user_id support to session creation:
```typescript
// In sessionApi object
create: async (userId?: string) => {
  const response = await fetch(`${API_URL}/api/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: userId ? JSON.stringify({ user_id: userId }) : undefined,
  });
  // ... rest of implementation
}
```

**2. Update `frontend/hooks/use-session.ts`** - Pass user ID when creating sessions:
```typescript
// Modify createNewSession to accept optional userId
const createNewSession = useCallback(async (userId?: string) => {
  const session = await sessionApi.create(userId);
  // ... rest of implementation
}, []);
```

**3. Connect auth and chat sessions** - In components that create sessions:
```typescript
const { session: authSession } = useAuth();
const { createNewSession } = useSession();

// When creating a new chat, pass the authenticated user's ID
const handleNewChat = async () => {
  await createNewSession(authSession?.user?.id);
};
```

## Security Checklist

- [ ] CSRF protection enabled (default in BetterAuth)
- [ ] Secure cookie settings (`secure: true` in production)
- [ ] HttpOnly cookies for session
- [ ] Rate limiting on auth endpoints
- [ ] No user enumeration in error messages
- [ ] Session invalidation on password change
- [ ] Proper redirect after login/logout

## OAuth Provider Setup

For Google OAuth:
1. Create project in Google Cloud Console
2. Configure OAuth consent screen
3. Create OAuth 2.0 credentials
4. Add authorized redirect URI: `http://localhost:3000/api/auth/callback/google`

For GitHub OAuth:
1. Go to GitHub Developer Settings
2. Create new OAuth App
3. Set callback URL: `http://localhost:3000/api/auth/callback/github`

## Environment Variables to Add

```env
# .env.local (frontend)
DATABASE_URL=postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres
BETTER_AUTH_SECRET=your-random-secret-min-32-chars
BETTER_AUTH_URL=http://localhost:3000
NEXT_PUBLIC_APP_URL=http://localhost:3000  # Required for auth-client.ts

# OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
```

**Note:** Also update `frontend/.env.example` with these new variables (without sensitive values).

## Component Style Guide

Match existing ChatTwelve shadcn/ui patterns:
- Use `Button` from `@/components/ui/button`
- Use `Input` from `@/components/ui/input`
- Use `Card` for form containers
- Dark mode support via Tailwind classes (app uses `className="dark"` on html)
- Loading states with `Loader2` spinner from lucide-react
- Toast notifications via `useToast` hook from `@/hooks/use-toast`

**Toast usage pattern (match existing codebase):**
```typescript
import { useToast } from "@/hooks/use-toast";

const { toast } = useToast();

// Success
toast({ title: "Success", description: "Account created!" });

// Error (use variant on the toast component, not in the call)
toast({ title: "Error", description: "Something went wrong" });
```

## Testing Auth

Add to `frontend/tests/auth.spec.ts`:
```typescript
test('user can sign up', async ({ page }) => {
  await page.goto('/signup');
  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="password"]', 'securepassword123');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/');
});
```
