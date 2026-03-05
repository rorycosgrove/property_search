-- PostGIS initialization script
-- Runs on first database creation

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- pgvector for future embedding support
-- CREATE EXTENSION IF NOT EXISTS vector;
