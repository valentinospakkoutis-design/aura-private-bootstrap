-- PostgreSQL Database Setup Script for AURA
-- Run this script to create the database and user

-- Create database
CREATE DATABASE aura_db;

-- Create user (optional, can use postgres user)
-- CREATE USER aura_user WITH PASSWORD 'aura_password_2025';
-- GRANT ALL PRIVILEGES ON DATABASE aura_db TO aura_user;

-- Connect to aura_db and run migrations
-- \c aura_db

-- Tables will be created automatically by SQLAlchemy on first run
-- Or run: python -c "from database.connection import init_db; init_db()"

