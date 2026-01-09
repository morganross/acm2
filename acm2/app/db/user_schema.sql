-- Per-User Database Schema
-- Each user gets their own database file (user_X.db)

-- Store evaluation runs
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Run configuration
    system_prompt TEXT,
    user_prompt TEXT,
    model_ids TEXT,  -- JSON array
    criteria TEXT,   -- JSON array
    
    -- Results
    results TEXT,    -- JSON object
    error TEXT,
    
    -- Metadata
    total_cost REAL,
    total_tokens INTEGER,
    duration_seconds REAL
);

-- Store provider API keys (encrypted)
CREATE TABLE IF NOT EXISTS provider_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL UNIQUE,  -- 'openai', 'anthropic', 'google'
    encrypted_key TEXT NOT NULL,    -- AES-256 encrypted API key
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store usage statistics
CREATE TABLE IF NOT EXISTS usage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0.0,
    run_count INTEGER DEFAULT 0,
    UNIQUE(date, provider, model_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_usage_date ON usage_stats(date DESC);
