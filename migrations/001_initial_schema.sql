-- ChatTwelve Phase 3: PostgreSQL Schema Migration
-- Run this SQL in your Supabase PostgreSQL database
-- Compatible with self-hosted Supabase

-- =====================================================
-- PROFILES TABLE
-- Extends BetterAuth user with app-specific settings
-- =====================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id TEXT PRIMARY KEY,  -- References BetterAuth user.id (TEXT, not UUID)
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    preferences JSONB DEFAULT '{}'::jsonb,  -- Theme, default prompt, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for email lookups
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);

-- =====================================================
-- CHAT_SESSIONS TABLE
-- Stores conversation sessions linked to users
-- =====================================================
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    -- Rate limiting (migrated from SQLite sessions table)
    request_count INTEGER DEFAULT 0,
    request_window_start TIMESTAMPTZ DEFAULT NOW(),
    -- Metadata for extensibility
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON public.chat_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_message ON public.chat_sessions(last_message_at DESC);

-- =====================================================
-- CHAT_MESSAGES TABLE
-- Individual messages (replaces JSON context array)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    model TEXT,  -- AI model that generated assistant messages
    metadata JSONB DEFAULT '{}'::jsonb,  -- Tools used, response time, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for message retrieval
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON public.chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON public.chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created ON public.chat_messages(session_id, created_at);

-- =====================================================
-- SYSTEM_PROMPTS TABLE
-- User-customizable AI system prompts
-- =====================================================
CREATE TABLE IF NOT EXISTS public.system_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES public.profiles(id) ON DELETE CASCADE,  -- NULL for system defaults
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- Unique constraint: one prompt name per user (or system-wide if user_id is NULL)
    UNIQUE(user_id, name)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_system_prompts_active ON public.system_prompts(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_system_prompts_user_id ON public.system_prompts(user_id);

-- =====================================================
-- DEFAULT SYSTEM PROMPT
-- Pre-seed with trading-focused prompt
-- =====================================================
INSERT INTO public.system_prompts (user_id, name, prompt, description, is_active)
VALUES (
    NULL,  -- System default (not user-specific)
    'Default Trading Assistant',
    'You are a helpful trading and market analysis assistant. You provide real-time market data and analysis to help users understand financial markets.

Your capabilities:
- Fetch current prices for stocks, forex, crypto, and commodities
- Provide detailed quotes with OHLC, volume, and 52-week ranges
- Show historical price data and trends
- Calculate technical indicators (RSI, MACD, SMA, EMA, Bollinger Bands, etc.)
- Convert between currencies
- Search for financial news and market updates

Guidelines:
- Always use available tools to fetch real-time data rather than relying on training data
- Present numerical data clearly with appropriate formatting
- Explain market movements and technical indicators in plain English
- Acknowledge when data might be delayed or unavailable
- Never provide financial advice - only factual market data and analysis',
    'Default system prompt for market data queries',
    TRUE
) ON CONFLICT (user_id, name) DO NOTHING;

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for auto-updating updated_at
DROP TRIGGER IF EXISTS update_profiles_updated_at ON public.profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON public.chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON public.chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_system_prompts_updated_at ON public.system_prompts;
CREATE TRIGGER update_system_prompts_updated_at
    BEFORE UPDATE ON public.system_prompts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to update last_message_at on new message
CREATE OR REPLACE FUNCTION update_session_last_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.chat_sessions
    SET last_message_at = NOW(), updated_at = NOW()
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_session_on_message ON public.chat_messages;
CREATE TRIGGER update_session_on_message
    AFTER INSERT ON public.chat_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_session_last_message();

-- =====================================================
-- ROW LEVEL SECURITY (Optional)
-- Since we use BetterAuth (not Supabase Auth), auth.uid() is not available
-- All operations go through FastAPI backend with service role
-- =====================================================

-- Enable RLS (backend uses service role which bypasses RLS)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_prompts ENABLE ROW LEVEL SECURITY;

-- Service role has full access (used by FastAPI backend)
-- Using DROP IF EXISTS + CREATE for idempotency (PostgreSQL doesn't support IF NOT EXISTS for policies)

DROP POLICY IF EXISTS "Service role full access to profiles" ON public.profiles;
CREATE POLICY "Service role full access to profiles"
    ON public.profiles FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access to chat_sessions" ON public.chat_sessions;
CREATE POLICY "Service role full access to chat_sessions"
    ON public.chat_sessions FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access to chat_messages" ON public.chat_messages;
CREATE POLICY "Service role full access to chat_messages"
    ON public.chat_messages FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access to system_prompts" ON public.system_prompts;
CREATE POLICY "Service role full access to system_prompts"
    ON public.system_prompts FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Anon key has read-only access to system prompts only
DROP POLICY IF EXISTS "Anon can read system prompts" ON public.system_prompts;
CREATE POLICY "Anon can read system prompts"
    ON public.system_prompts FOR SELECT
    TO anon
    USING (user_id IS NULL);  -- Only system defaults

-- =====================================================
-- GRANTS
-- =====================================================
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT SELECT ON public.system_prompts TO anon;
