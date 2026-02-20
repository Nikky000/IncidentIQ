-- ============================================
-- IncidentIQ Database Initialization Script
-- Run on first deployment
-- ============================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- ============================================
-- Default Configuration Values
-- ============================================

INSERT INTO configurations (id, key, value, value_type, is_secret, description) VALUES
    (uuid_generate_v4(), 'LLM_MODEL', 'anthropic/claude-3-5-sonnet-20241022', 'string', false, 'Default LLM model (LiteLLM format)'),
    (uuid_generate_v4(), 'EMBEDDING_MODEL', 'openai/text-embedding-3-small', 'string', false, 'Default embedding model'),
    (uuid_generate_v4(), 'EXACT_MATCH_THRESHOLD', '0.92', 'float', false, 'Minimum similarity for EXACT MATCH'),
    (uuid_generate_v4(), 'PARTIAL_MATCH_THRESHOLD', '0.70', 'float', false, 'Minimum similarity for PARTIAL MATCH'),
    (uuid_generate_v4(), 'MIN_MATCH_THRESHOLD', '0.50', 'float', false, 'Minimum similarity to show'),
    (uuid_generate_v4(), 'MAX_SIMILAR_INCIDENTS', '5', 'int', false, 'Maximum incidents to return'),
    (uuid_generate_v4(), 'SEMANTIC_CACHE_ENABLED', 'true', 'bool', false, 'Enable semantic caching for LLM'),
    (uuid_generate_v4(), 'SEMANTIC_CACHE_THRESHOLD', '0.95', 'float', false, 'Similarity threshold for semantic cache hits')
ON CONFLICT (key) DO NOTHING;

-- ============================================
-- Indexes for Performance
-- ============================================

-- Incidents
CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents(service);
CREATE INDEX IF NOT EXISTS idx_incidents_error_type ON incidents(error_type);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);

-- Full-text search on title and description
CREATE INDEX IF NOT EXISTS idx_incidents_search ON incidents 
    USING GIN (to_tsvector('english', title || ' ' || COALESCE(description, '')));

-- Expert skills
CREATE INDEX IF NOT EXISTS idx_expert_skills_skill ON expert_skills(skill_type, skill_name);
CREATE INDEX IF NOT EXISTS idx_expert_skills_proficiency ON expert_skills(proficiency_score DESC);

-- Search logs for analytics
CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_logs_user ON search_logs(user_id);

-- ============================================
-- Functions
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_incidents_updated_at BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_experts_updated_at BEFORE UPDATE ON experts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_configurations_updated_at BEFORE UPDATE ON configurations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
