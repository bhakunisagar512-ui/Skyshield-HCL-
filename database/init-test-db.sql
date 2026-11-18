-- Runs once when the Docker database is first created.
CREATE DATABASE skyshield_test OWNER skyshield;
\c skyshield
CREATE EXTENSION IF NOT EXISTS vector;
\c skyshield_test
CREATE EXTENSION IF NOT EXISTS vector;
