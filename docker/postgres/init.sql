-- PostGIS initialization script
-- Runs on first database creation

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- pgvector for future embedding support
-- CREATE EXTENSION IF NOT EXISTS vector;
