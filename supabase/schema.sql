-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================
-- USERS TABLE
-- =========================
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    age INTEGER,
    gender TEXT,
    medical_conditions TEXT,
    stress_trigger TEXT,
    social_preference TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- =========================
-- MESSAGES TABLE
-- =========================
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    emotion TEXT,
    sentiment_score NUMERIC(5,2),
    risk_level TEXT,
    is_user BOOLEAN DEFAULT true,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- =========================
-- EMOTION LOGS
-- =========================
CREATE TABLE IF NOT EXISTS public.emotion_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    predominant_emotion TEXT,
    avg_sentiment NUMERIC(5,2),
    recorded_date DATE DEFAULT CURRENT_DATE NOT NULL
);

-- =========================
-- MOOD ENTRIES
-- =========================
CREATE TABLE IF NOT EXISTS public.mood_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    mood_score INTEGER CHECK (mood_score >= 1 AND mood_score <= 10),
    journal_text TEXT,
    stress_level INTEGER CHECK (stress_level >= 1 AND stress_level <= 10),
    predicted_stress_increase NUMERIC(5,2) DEFAULT 0.00,
    recorded_date DATE DEFAULT CURRENT_DATE NOT NULL
);

-- =========================
-- PHQ-9 RESULTS
-- =========================
CREATE TABLE IF NOT EXISTS public.phq9_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    score INTEGER CHECK (score >= 0 AND score <= 27),
    classification TEXT,
    recorded_date DATE DEFAULT CURRENT_DATE NOT NULL
);

-- =========================
-- WELLNESS PLANS
-- =========================
CREATE TABLE IF NOT EXISTS public.wellness_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    plan_details JSONB,
    generated_date DATE DEFAULT CURRENT_DATE NOT NULL
);

-- =========================
-- REALTIME (SAFE ADD)
-- =========================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'messages'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.messages;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'mood_entries'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.mood_entries;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'phq9_results'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.phq9_results;
    END IF;
END $$;

-- =========================
-- ENABLE RLS
-- =========================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emotion_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mood_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.phq9_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wellness_plans ENABLE ROW LEVEL SECURITY;

-- =========================
-- DROP OLD POLICIES & CREATE SECURE ONES (SAFE)
-- =========================
DO $$
BEGIN
    -- Drop old MVP policies
    DROP POLICY IF EXISTS "Allow public read/write for MVP" ON public.users;
    DROP POLICY IF EXISTS "Allow public read/write for MVP" ON public.messages;
    DROP POLICY IF EXISTS "Allow public read/write for MVP" ON public.emotion_logs;
    DROP POLICY IF EXISTS "Allow public read/write for MVP" ON public.mood_entries;
    DROP POLICY IF EXISTS "Allow public read/write for MVP" ON public.phq9_results;
    DROP POLICY IF EXISTS "Allow public read/write for MVP" ON public.wellness_plans;

    -- Drop new secure policies if they exist (for idempotency)
    DROP POLICY IF EXISTS "Users can manage own data" ON public.users;
    DROP POLICY IF EXISTS "Users can manage own messages" ON public.messages;
    DROP POLICY IF EXISTS "Users can manage own emotion logs" ON public.emotion_logs;
    DROP POLICY IF EXISTS "Users can manage own mood entries" ON public.mood_entries;
    DROP POLICY IF EXISTS "Users can manage own phq9 results" ON public.phq9_results;
    DROP POLICY IF EXISTS "Users can manage own wellness plans" ON public.wellness_plans;

    -- Create new secure policies
    CREATE POLICY "Users can manage own data"
    ON public.users
    FOR ALL
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

    CREATE POLICY "Users can manage own messages"
    ON public.messages
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can manage own emotion logs"
    ON public.emotion_logs
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can manage own mood entries"
    ON public.mood_entries
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can manage own phq9 results"
    ON public.phq9_results
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can manage own wellness plans"
    ON public.wellness_plans
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
END $$;
