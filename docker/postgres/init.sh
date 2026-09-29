#!/bin/sh
# Runs once, on first start of an empty data volume.
# Creates the demo database and a read-only role that DataPilot uses to query it.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE DATABASE sales_demo OWNER $POSTGRES_USER;
CREATE ROLE datapilot_reader LOGIN PASSWORD '$READER_PASSWORD';
ALTER ROLE datapilot_reader SET default_transaction_read_only = on;
ALTER ROLE datapilot_reader SET statement_timeout = '30s';
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname sales_demo <<SQL
REVOKE ALL ON DATABASE sales_demo FROM PUBLIC;
GRANT CONNECT ON DATABASE sales_demo TO datapilot_reader;
GRANT USAGE ON SCHEMA public TO datapilot_reader;
-- Tables are created later by the seeder (running as $POSTGRES_USER).
ALTER DEFAULT PRIVILEGES FOR ROLE $POSTGRES_USER IN SCHEMA public GRANT SELECT ON TABLES TO datapilot_reader;
SQL
