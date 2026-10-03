-- ============================================================
-- PostgreSQL Initialization Script for sakila_dw
-- 
-- This script creates:
-- 1. etl schema for audit tables
-- 2. staging schema for staging tables
-- 3. mart schema for data mart
-- 4. Required tables for the ETL pipeline
-- 
-- Note: This runs when the container first starts up
-- ============================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS etl;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;

-- Set search path
SET search_path TO etl, staging, mart, public;

-- ============================================================
-- ETL Schema - Audit Tables
-- ============================================================

-- Batch tracking
CREATE TABLE IF NOT EXISTS etl.batch (
    batch_id SERIAL PRIMARY KEY,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    finished_at TIMESTAMP
);

-- Load log
CREATE TABLE IF NOT EXISTS etl.load_log (
    log_id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    row_count INTEGER,
    started_at TIMESTAMP DEFAULT NOW(),
    finished_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (batch_id) REFERENCES etl.batch(batch_id)
);

-- Data quality results
CREATE TABLE IF NOT EXISTS etl.dq_results (
    result_id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL,
    check_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'critical',
    details TEXT,
    checked_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (batch_id) REFERENCES etl.batch(batch_id)
);

-- ============================================================
-- Staging Schema - Source Data Tables
-- ============================================================

-- Customer data from Sakila source
CREATE TABLE IF NOT EXISTS staging.customer (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR(45) NOT NULL,
    last_name VARCHAR(45) NOT NULL,
    email VARCHAR(50),
    address VARCHAR(50) NOT NULL,
    district VARCHAR(20) NOT NULL,
    city VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL,
    create_date TIMESTAMP NOT NULL,
    last_update TIMESTAMP NOT NULL
);

-- Film data from Sakila source
CREATE TABLE IF NOT EXISTS staging.film (
    film_id INTEGER PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    release_year YEAR,
    rental_rate DECIMAL(4,2) NOT NULL,
    rental_duration INTEGER NOT NULL,
    replacement_cost DECIMAL(5,2) NOT NULL,
    rating VARCHAR(10) DEFAULT 'G',
    length INTEGER,
    primary_category VARCHAR(25),
    last_update TIMESTAMP NOT NULL
);

-- Category data from Sakila source
CREATE TABLE IF NOT EXISTS staging.category (
    category_id INTEGER PRIMARY KEY,
    name VARCHAR(25) NOT NULL,
    last_update TIMESTAMP NOT NULL
);

-- Film Category bridge table
CREATE TABLE IF NOT EXISTS staging.film_category (
    film_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    last_update TIMESTAMP NOT NULL,
    PRIMARY KEY (film_id, category_id),
    FOREIGN KEY (film_id) REFERENCES staging.film(film_id),
    FOREIGN KEY (category_id) REFERENCES staging.category(category_id)
);

-- Store data from Sakila source
CREATE TABLE IF NOT EXISTS staging.store (
    store_id INTEGER PRIMARY KEY,
    manager_staff_id INTEGER NOT NULL,
    address VARCHAR(50) NOT NULL,
    district VARCHAR(20) NOT NULL,
    city VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL,
    last_update TIMESTAMP NOT NULL
);

-- Staff data from Sakila source
CREATE TABLE IF NOT EXISTS staging.staff (
    staff_id INTEGER PRIMARY KEY,
    first_name VARCHAR(45) NOT NULL,
    last_name VARCHAR(45) NOT NULL,
    email VARCHAR(50),
    store_id INTEGER NOT NULL,
    active BOOLEAN NOT NULL,
    last_update TIMESTAMP NOT NULL
);

-- Rental data from Sakila source
CREATE TABLE IF NOT EXISTS staging.rental (
    rental_id INTEGER PRIMARY KEY,
    rental_date TIMESTAMP NOT NULL,
    return_date TIMESTAMP NOT NULL,
    inventory_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    staff_id INTEGER NOT NULL,
    film_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    last_update TIMESTAMP NOT NULL
);

-- Payment data from Sakila source
CREATE TABLE IF NOT EXISTS staging.payment (
    payment_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    staff_id INTEGER NOT NULL,
    rental_id INTEGER NOT NULL,
    amount DECIMAL(5,2) NOT NULL,
    payment_date TIMESTAMP NOT NULL,
    last_update TIMESTAMP NOT NULL
);

-- ============================================================
-- Mart Schema - Data Warehouse
-- ============================================================

-- Date dimension
CREATE TABLE IF NOT EXISTS mart.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR(10) NOT NULL,
    day INTEGER NOT NULL,
    day_name VARCHAR(10) NOT NULL,
    week_of_year INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

-- Customer dimension
CREATE TABLE IF NOT EXISTS mart.dim_customer (
    customer_sk INTEGER PRIMARY KEY,
    first_name VARCHAR(45) NOT NULL,
    last_name VARCHAR(45) NOT NULL,
    email VARCHAR(50),
    address VARCHAR(50) NOT NULL,
    district VARCHAR(20) NOT NULL,
    city VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL,
    create_date TIMESTAMP NOT NULL,
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Film dimension
CREATE TABLE IF NOT EXISTS mart.dim_film (
    film_sk INTEGER PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    release_year YEAR,
    rental_rate DECIMAL(4,2) NOT NULL,
    rental_duration INTEGER NOT NULL,
    replacement_cost DECIMAL(5,2) NOT NULL,
    rating VARCHAR(10) DEFAULT 'G',
    length INTEGER,
    primary_category VARCHAR(25),
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Category dimension
CREATE TABLE IF NOT EXISTS mart.dim_category (
    category_id INTEGER PRIMARY KEY,
    name VARCHAR(25) NOT NULL,
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Store dimension
CREATE TABLE IF NOT EXISTS mart.dim_store (
    store_sk INTEGER PRIMARY KEY,
    manager_staff_sk INTEGER NOT NULL,
    address VARCHAR(50) NOT NULL,
    district VARCHAR(20) NOT NULL,
    city VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL,
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Staff dimension
CREATE TABLE IF NOT EXISTS mart.dim_staff (
    staff_sk INTEGER PRIMARY KEY,
    first_name VARCHAR(45) NOT NULL,
    last_name VARCHAR(45) NOT NULL,
    email VARCHAR(50),
    store_sk INTEGER NOT NULL,
    active BOOLEAN NOT NULL,
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Bridge table for film categories
CREATE TABLE IF NOT EXISTS mart.bridge_film_category (
    film_sk INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (film_sk, category_id),
    FOREIGN KEY (film_sk) REFERENCES mart.dim_film(film_sk),
    FOREIGN KEY (category_id) REFERENCES mart.dim_category(category_id)
);

-- Rental fact table
CREATE TABLE IF NOT EXISTS mart.fact_rental (
    rental_id INTEGER PRIMARY KEY,
    rental_date_key INTEGER NOT NULL,
    customer_sk INTEGER NOT NULL,
    film_sk INTEGER NOT NULL,
    store_sk INTEGER NOT NULL,
    staff_sk INTEGER NOT NULL,
    rental_date TIMESTAMP NOT NULL,
    return_date TIMESTAMP NOT NULL,
    rental_duration_days DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (rental_date_key) REFERENCES mart.dim_date(date_key),
    FOREIGN KEY (customer_sk) REFERENCES mart.dim_customer(customer_sk),
    FOREIGN KEY (film_sk) REFERENCES mart.dim_film(film_sk),
    FOREIGN KEY (store_sk) REFERENCES mart.dim_store(store_sk),
    FOREIGN KEY (staff_sk) REFERENCES mart.dim_staff(staff_sk)
);

-- Payment fact table
CREATE TABLE IF NOT EXISTS mart.fact_payment (
    payment_id INTEGER PRIMARY KEY,
    payment_date_key INTEGER NOT NULL,
    customer_sk INTEGER NOT NULL,
    staff_sk INTEGER NOT NULL,
    rental_id INTEGER NOT NULL,
    amount DECIMAL(5,2) NOT NULL,
    payment_date TIMESTAMP NOT NULL,
    FOREIGN KEY (payment_date_key) REFERENCES mart.dim_date(date_key),
    FOREIGN KEY (customer_sk) REFERENCES mart.dim_customer(customer_sk),
    FOREIGN KEY (staff_sk) REFERENCES mart.dim_staff(staff_sk)
);

-- ============================================================
-- Grants (for development access)
-- ============================================================

GRANT ALL PRIVILEGES ON SCHEMA etl TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA staging TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA mart TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA etl TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA staging TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA mart TO postgres;

-- Create read-only user for ETL (optional)
-- CREATE USER etl_user WITH PASSWORD 'etl_password';
-- GRANT CONNECT ON DATABASE sakila_dw TO etl_user;
-- GRANT USAGE ON SCHEMA staging TO etl_user;
-- GRANT SELECT ON ALL TABLES IN SCHEMA staging TO etl_user;
-- GRANT USAGE ON SCHEMA mart TO etl_user;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA mart TO etl_user;
-- GRANT USAGE ON SCHEMA etl TO etl_user;
-- GRANT INSERT, SELECT ON ALL TABLES IN SCHEMA etl TO etl_user;

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_fact_rental_date ON mart.fact_rental(rental_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_payment_date ON mart.fact_payment(payment_date_key);

-- Log completion
RAISE NOTICE 'PostgreSQL database initialized for sakila_dw ETL pipeline';
