-- PostgreSQL Schema for bin2nlp Hybrid Storage System
-- Combines PostgreSQL for structured data with file storage for large results

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Custom types and enums
CREATE TYPE job_status AS ENUM (
    'pending',
    'in_progress', 
    'completed',
    'failed',
    'cancelled'
);

CREATE TYPE job_priority AS ENUM (
    'low',
    'normal', 
    'high',
    'urgent'
);

CREATE TYPE rate_limit_scope AS ENUM (
    'global',
    'api_key',
    'ip_address'
);

-- Jobs table for queue management
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status job_status NOT NULL DEFAULT 'pending',
    priority job_priority NOT NULL DEFAULT 'normal',
    
    -- File information
    file_hash VARCHAR(64) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_reference TEXT NOT NULL,
    
    -- Analysis configuration (stored as JSONB for flexibility)
    analysis_config JSONB NOT NULL,
    
    -- Result storage (points to file storage)
    result_file_path VARCHAR(500),
    error_message TEXT,
    
    -- Progress tracking
    progress_percentage REAL DEFAULT 0.0,
    current_stage VARCHAR(100),
    worker_id VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Request context
    submitted_by VARCHAR(100),
    callback_url TEXT,
    correlation_id VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Performance tracking
    processing_time_seconds INTEGER,
    estimated_completion_seconds INTEGER
);

-- Indexes for job queue operations
CREATE INDEX idx_jobs_status_priority ON jobs (status, priority, created_at);
CREATE INDEX idx_jobs_file_hash ON jobs (file_hash);
CREATE INDEX idx_jobs_worker_id ON jobs (worker_id);
CREATE INDEX idx_jobs_created_at ON jobs (created_at);
CREATE INDEX idx_jobs_submitted_by ON jobs (submitted_by);

-- Cache metadata table (actual cache data stored in files)
CREATE TABLE cache_entries (
    cache_key VARCHAR(255) PRIMARY KEY,
    file_hash VARCHAR(64) NOT NULL,
    config_hash VARCHAR(32) NOT NULL,
    
    -- File storage reference
    file_path VARCHAR(500) NOT NULL,
    
    -- Cache metadata
    cache_version VARCHAR(10) DEFAULT '1.0',
    tags TEXT[] DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Statistics
    access_count INTEGER DEFAULT 0,
    data_size_bytes BIGINT DEFAULT 0
);

-- Indexes for cache operations
CREATE INDEX idx_cache_expires_at ON cache_entries (expires_at);
CREATE INDEX idx_cache_file_hash ON cache_entries (file_hash);
CREATE INDEX idx_cache_tags ON cache_entries USING GIN (tags);
CREATE INDEX idx_cache_created_at ON cache_entries (created_at);

-- Rate limiting table
CREATE TABLE rate_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scope rate_limit_scope NOT NULL,
    identifier VARCHAR(255) NOT NULL, -- API key, IP address, or 'global'
    
    -- Rate limit tracking
    request_count INTEGER DEFAULT 1,
    window_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    window_size_seconds INTEGER NOT NULL,
    
    -- Limits
    max_requests INTEGER NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for rate limiting
CREATE UNIQUE INDEX idx_rate_limits_scope_identifier ON rate_limits (scope, identifier, window_start);
CREATE INDEX idx_rate_limits_window_start ON rate_limits (window_start);

-- Sessions table for API key and user session management
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_key VARCHAR(255) UNIQUE NOT NULL,
    
    -- Session data (stored as JSONB for flexibility)
    session_data JSONB DEFAULT '{}'::jsonb,
    
    -- API key information
    api_key_hash VARCHAR(64),
    api_key_prefix VARCHAR(10),
    user_tier VARCHAR(50) DEFAULT 'basic',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Session metadata
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for session operations
CREATE INDEX idx_sessions_session_key ON sessions (session_key);
CREATE INDEX idx_sessions_api_key_hash ON sessions (api_key_hash);
CREATE INDEX idx_sessions_expires_at ON sessions (expires_at);
CREATE INDEX idx_sessions_last_accessed ON sessions (last_accessed);

-- System statistics and monitoring
CREATE TABLE system_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stat_key VARCHAR(100) NOT NULL,
    stat_value BIGINT DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Index for system stats
CREATE UNIQUE INDEX idx_system_stats_key ON system_stats (stat_key);

-- Worker heartbeat tracking
CREATE TABLE worker_heartbeats (
    worker_id VARCHAR(100) PRIMARY KEY,
    
    -- Worker information
    worker_type VARCHAR(50) DEFAULT 'decompilation',
    status VARCHAR(20) DEFAULT 'active',
    current_job_id UUID,
    
    -- Timestamps
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Worker metadata
    hostname VARCHAR(255),
    process_id INTEGER,
    version VARCHAR(20),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Index for worker heartbeats
CREATE INDEX idx_worker_heartbeats_last_heartbeat ON worker_heartbeats (last_heartbeat);
CREATE INDEX idx_worker_heartbeats_current_job ON worker_heartbeats (current_job_id);

-- File storage tracking (optional - for monitoring and cleanup)
CREATE TABLE file_storage_entries (
    file_path VARCHAR(500) PRIMARY KEY,
    
    -- File metadata
    original_filename VARCHAR(255),
    content_type VARCHAR(100),
    file_size_bytes BIGINT,
    file_hash VARCHAR(64),
    
    -- Storage metadata
    storage_type VARCHAR(20) DEFAULT 'cache', -- 'cache', 'result', 'upload'
    reference_count INTEGER DEFAULT 1,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for file storage tracking
CREATE INDEX idx_file_storage_expires_at ON file_storage_entries (expires_at);
CREATE INDEX idx_file_storage_file_hash ON file_storage_entries (file_hash);
CREATE INDEX idx_file_storage_storage_type ON file_storage_entries (storage_type);

-- Triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rate_limits_updated_at BEFORE UPDATE ON rate_limits 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_stats_updated_at BEFORE UPDATE ON system_stats 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Functions for job queue operations

-- Atomic job dequeue function
CREATE OR REPLACE FUNCTION dequeue_next_job(p_worker_id VARCHAR(100))
RETURNS TABLE (
    job_id UUID,
    file_hash VARCHAR(64),
    filename VARCHAR(255),
    file_reference TEXT,
    analysis_config JSONB,
    priority job_priority,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    UPDATE jobs 
    SET status = 'in_progress',
        worker_id = p_worker_id,
        started_at = NOW(),
        updated_at = NOW()
    WHERE id = (
        SELECT j.id
        FROM jobs j
        WHERE j.status = 'pending'
        ORDER BY 
            CASE j.priority 
                WHEN 'urgent' THEN 0
                WHEN 'high' THEN 1  
                WHEN 'normal' THEN 2
                WHEN 'low' THEN 3
            END,
            j.created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING 
        jobs.id,
        jobs.file_hash,
        jobs.filename, 
        jobs.file_reference,
        jobs.analysis_config,
        jobs.priority,
        jobs.metadata;
END;
$$ LANGUAGE plpgsql;

-- Rate limiting check function
CREATE OR REPLACE FUNCTION check_rate_limit(
    p_scope rate_limit_scope,
    p_identifier VARCHAR(255),
    p_window_seconds INTEGER,
    p_max_requests INTEGER
) RETURNS BOOLEAN AS $$
DECLARE
    current_count INTEGER;
    window_start_time TIMESTAMP WITH TIME ZONE;
BEGIN
    window_start_time := NOW() - (p_window_seconds || ' seconds')::INTERVAL;
    
    -- Clean up old entries first
    DELETE FROM rate_limits 
    WHERE scope = p_scope 
    AND identifier = p_identifier 
    AND window_start < window_start_time;
    
    -- Get current count
    SELECT COALESCE(SUM(request_count), 0) INTO current_count
    FROM rate_limits
    WHERE scope = p_scope 
    AND identifier = p_identifier
    AND window_start >= window_start_time;
    
    -- Check if we're under the limit
    IF current_count < p_max_requests THEN
        -- Increment counter
        INSERT INTO rate_limits (scope, identifier, window_size_seconds, max_requests, request_count)
        VALUES (p_scope, p_identifier, p_window_seconds, p_max_requests, 1)
        ON CONFLICT (scope, identifier, window_start) 
        DO UPDATE SET 
            request_count = rate_limits.request_count + 1,
            updated_at = NOW();
        
        RETURN TRUE;
    ELSE
        RETURN FALSE;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Cache cleanup function
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM cache_entries 
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Update statistics
    INSERT INTO system_stats (stat_key, stat_value)
    VALUES ('cache_cleanup_last_run', EXTRACT(EPOCH FROM NOW())::BIGINT)
    ON CONFLICT (stat_key) 
    DO UPDATE SET 
        stat_value = EXTRACT(EPOCH FROM NOW())::BIGINT,
        updated_at = NOW();
        
    INSERT INTO system_stats (stat_key, stat_value)
    VALUES ('cache_entries_cleaned_total', deleted_count)
    ON CONFLICT (stat_key)
    DO UPDATE SET 
        stat_value = system_stats.stat_value + deleted_count,
        updated_at = NOW();
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Views for monitoring and analytics

-- Job queue overview
CREATE VIEW job_queue_stats AS
SELECT 
    status,
    priority,
    COUNT(*) as job_count,
    AVG(processing_time_seconds) as avg_processing_time,
    MIN(created_at) as oldest_job,
    MAX(created_at) as newest_job
FROM jobs
GROUP BY status, priority
ORDER BY 
    CASE priority 
        WHEN 'urgent' THEN 0
        WHEN 'high' THEN 1
        WHEN 'normal' THEN 2  
        WHEN 'low' THEN 3
    END,
    CASE status
        WHEN 'pending' THEN 0
        WHEN 'in_progress' THEN 1
        WHEN 'completed' THEN 2
        WHEN 'failed' THEN 3
        WHEN 'cancelled' THEN 4
    END;

-- Cache performance stats
CREATE VIEW cache_performance AS
SELECT 
    COUNT(*) as total_entries,
    COUNT(*) FILTER (WHERE expires_at > NOW()) as active_entries,
    COUNT(*) FILTER (WHERE expires_at <= NOW()) as expired_entries,
    AVG(access_count) as avg_access_count,
    SUM(data_size_bytes) as total_size_bytes,
    AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) as avg_age_seconds
FROM cache_entries;

-- Rate limiting overview
CREATE VIEW rate_limit_stats AS
SELECT 
    scope,
    COUNT(DISTINCT identifier) as unique_identifiers,
    SUM(request_count) as total_requests,
    AVG(request_count) as avg_requests_per_window,
    MAX(request_count) as max_requests_in_window
FROM rate_limits
WHERE window_start > NOW() - INTERVAL '1 hour'
GROUP BY scope;

-- Initial system statistics
INSERT INTO system_stats (stat_key, stat_value) VALUES 
    ('jobs_total', 0),
    ('jobs_completed', 0),
    ('jobs_failed', 0),
    ('cache_hits', 0),
    ('cache_misses', 0),
    ('cache_sets', 0),
    ('rate_limit_hits', 0),
    ('rate_limit_blocks', 0)
ON CONFLICT (stat_key) DO NOTHING;