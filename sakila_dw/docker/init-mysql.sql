-- ============================================================
-- MySQL Initialization Script for sakila_dw
-- 
-- This script sets up the Sakila sample database for the ETL pipeline.
-- 
-- Note: This runs when the container first starts up
-- ============================================================

-- Create the sakila database if it doesn't exist
CREATE DATABASE IF NOT EXISTS sakila CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Use the sakila database
USE sakila;

-- ============================================================
-- Sakila Sample Database Schema
-- Based on the standard Sakila database
-- ============================================================

-- Actor table
CREATE TABLE IF NOT EXISTS actor (
    actor_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    first_name VARCHAR(45) NOT NULL,
    last_name VARCHAR(45) NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (actor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Address table
CREATE TABLE IF NOT EXISTS address (
    address_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    address VARCHAR(50) NOT NULL,
    address2 VARCHAR(50) DEFAULT NULL,
    district VARCHAR(20) NOT NULL,
    city_id SMALLINT UNSIGNED NOT NULL,
    postal_code VARCHAR(10) DEFAULT NULL,
    phone VARCHAR(20) NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (address_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Category table
CREATE TABLE IF NOT EXISTS category (
    category_id TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(25) NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- City table
CREATE TABLE IF NOT EXISTS city (
    city_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    city VARCHAR(50) NOT NULL,
    country_id SMALLINT UNSIGNED NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (city_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Country table
CREATE TABLE IF NOT EXISTS country (
    country_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    country VARCHAR(50) NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Customer table
CREATE TABLE IF NOT EXISTS customer (
    customer_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    store_id TINYINT UNSIGNED NOT NULL,
    first_name VARCHAR(45) NOT NULL,
    last_name VARCHAR(45) NOT NULL,
    email VARCHAR(50) DEFAULT NULL,
    address_id SMALLINT UNSIGNED NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    create_date DATETIME NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Film table
CREATE TABLE IF NOT EXISTS film (
    film_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT DEFAULT NULL,
    release_year YEAR DEFAULT NULL,
    language_id TINYINT UNSIGNED NOT NULL,
    original_language_id TINYINT UNSIGNED DEFAULT NULL,
    rental_duration SMALLINT UNSIGNED NOT NULL DEFAULT 3,
    rental_rate DECIMAL(4,2) NOT NULL DEFAULT 4.99,
    length SMALLINT UNSIGNED DEFAULT NULL,
    replacement_cost DECIMAL(5,2) NOT NULL DEFAULT 19.99,
    rating VARCHAR(10) DEFAULT 'G',
    special_features VARCHAR(100) DEFAULT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (film_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Film Category table (junction)
CREATE TABLE IF NOT EXISTS film_category (
    film_id SMALLINT UNSIGNED NOT NULL,
    category_id TINYINT UNSIGNED NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (film_id, category_id),
    FOREIGN KEY (film_id) REFERENCES film(film_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES category(category_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Inventory table
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    film_id SMALLINT UNSIGNED NOT NULL,
    store_id TINYINT UNSIGNED NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (inventory_id),
    FOREIGN KEY (film_id) REFERENCES film(film_id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES store(store_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Language table
CREATE TABLE IF NOT EXISTS language (
    language_id TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name CHAR(20) NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (language_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Payment table
CREATE TABLE IF NOT EXISTS payment (
    payment_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    customer_id SMALLINT UNSIGNED NOT NULL,
    staff_id TINYINT UNSIGNED NOT NULL,
    rental_id INT UNSIGNED DEFAULT NULL,
    amount DECIMAL(5,2) NOT NULL,
    payment_date DATETIME NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (payment_id),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE,
    FOREIGN KEY (rental_id) REFERENCES rental(rental_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Rental table
CREATE TABLE IF NOT EXISTS rental (
    rental_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    rental_date DATETIME NOT NULL,
    inventory_id INT UNSIGNED NOT NULL,
    customer_id SMALLINT UNSIGNED NOT NULL,
    return_date DATETIME DEFAULT NULL,
    staff_id TINYINT UNSIGNED NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (rental_id),
    FOREIGN KEY (inventory_id) REFERENCES inventory(inventory_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Staff table
CREATE TABLE IF NOT EXISTS staff (
    staff_id TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    first_name VARCHAR(45) NOT NULL,
    last_name VARCHAR(45) NOT NULL,
    address_id SMALLINT UNSIGNED NOT NULL,
    email VARCHAR(50) DEFAULT NULL,
    store_id TINYINT UNSIGNED NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    username VARCHAR(16) NOT NULL,
    password VARCHAR(40) DEFAULT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (staff_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Store table
CREATE TABLE IF NOT EXISTS store (
    store_id TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    manager_staff_id TINYINT UNSIGNED NOT NULL,
    address_id SMALLINT UNSIGNED NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (store_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Foreign Key Constraints
-- ============================================================

ALTER TABLE address ADD FOREIGN KEY (city_id) REFERENCES city(city_id) ON DELETE CASCADE;
ALTER TABLE city ADD FOREIGN KEY (country_id) REFERENCES country(country_id) ON DELETE CASCADE;
ALTER TABLE customer ADD FOREIGN KEY (store_id) REFERENCES store(store_id) ON DELETE CASCADE;
ALTER TABLE customer ADD FOREIGN KEY (address_id) REFERENCES address(address_id) ON DELETE CASCADE;
ALTER TABLE film ADD FOREIGN KEY (language_id) REFERENCES language(language_id) ON DELETE CASCADE;
ALTER TABLE film ADD FOREIGN KEY (original_language_id) REFERENCES language(language_id) ON DELETE SET NULL;
ALTER TABLE inventory ADD FOREIGN KEY (store_id) REFERENCES store(store_id) ON DELETE CASCADE;
ALTER TABLE staff ADD FOREIGN KEY (store_id) REFERENCES store(store_id) ON DELETE CASCADE;
ALTER TABLE staff ADD FOREIGN KEY (address_id) REFERENCES address(address_id) ON DELETE CASCADE;
ALTER TABLE store ADD FOREIGN KEY (manager_staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE;
ALTER TABLE store ADD FOREIGN KEY (address_id) REFERENCES address(address_id) ON DELETE CASCADE;

-- ============================================================
-- Insert Sample Data for Testing
-- ============================================================

-- Insert languages
INSERT INTO language (language_id, name) VALUES 
(1, 'English') ON DUPLICATE KEY UPDATE name = name;

-- Insert countries
INSERT INTO country (country_id, country) VALUES 
(1, 'United States') ON DUPLICATE KEY UPDATE country = country,
(2, 'Canada') ON DUPLICATE KEY UPDATE country = country;

-- Insert cities
INSERT INTO city (city_id, city, country_id) VALUES 
(1, 'New York', 1) ON DUPLICATE KEY UPDATE city = city,
(2, 'Los Angeles', 1) ON DUPLICATE KEY UPDATE city = city,
(3, 'Toronto', 2) ON DUPLICATE KEY UPDATE city = city;

-- Insert addresses
INSERT INTO address (address_id, address, district, city_id, postal_code, phone) VALUES 
(1, '123 Main St', 'Downtown', 1, '10001', '555-1234') ON DUPLICATE KEY UPDATE address = address,
(2, '456 Oak Ave', 'Midtown', 1, '90001', '555-5678') ON DUPLICATE KEY UPDATE address = address,
(3, '789 Maple Dr', 'North York', 3, 'M5V 3L9', '555-9012') ON DUPLICATE KEY UPDATE address = address;

-- Insert stores
INSERT INTO store (store_id, manager_staff_id, address_id) VALUES 
(1, 1, 1) ON DUPLICATE KEY UPDATE store_id = store_id,
(2, 2, 2) ON DUPLICATE KEY UPDATE store_id = store_id;

-- Insert staff
INSERT INTO staff (staff_id, first_name, last_name, address_id, email, store_id, active, username, password) VALUES 
(1, 'John', 'Doe', 1, 'john.doe@sakila.com', 1, TRUE, 'john_doe', 'password') ON DUPLICATE KEY UPDATE staff_id = staff_id,
(2, 'Jane', 'Smith', 2, 'jane.smith@sakila.com', 2, TRUE, 'jane_smith', 'password') ON DUPLICATE KEY UPDATE staff_id = staff_id;

-- Update store manager references
UPDATE store SET manager_staff_id = 1 WHERE store_id = 1;
UPDATE store SET manager_staff_id = 2 WHERE store_id = 2;

-- Insert customers
INSERT INTO customer (customer_id, store_id, first_name, last_name, email, address_id, active, create_date) VALUES 
(1, 1, 'Alice', 'Johnson', 'alice@email.com', 1, TRUE, NOW()) ON DUPLICATE KEY UPDATE customer_id = customer_id,
(2, 1, 'Bob', 'Williams', 'bob@email.com', 2, TRUE, NOW()) ON DUPLICATE KEY UPDATE customer_id = customer_id,
(3, 2, 'Charlie', 'Brown', 'charlie@email.com', 3, TRUE, NOW()) ON DUPLICATE KEY UPDATE customer_id = customer_id;

-- Insert categories
INSERT INTO category (category_id, name) VALUES 
(1, 'Action') ON DUPLICATE KEY UPDATE category_id = category_id,
(2, 'Comedy') ON DUPLICATE KEY UPDATE category_id = category_id,
(3, 'Drama') ON DUPLICATE KEY UPDATE category_id = category_id;

-- Insert films
INSERT INTO film (film_id, title, description, release_year, language_id, rental_duration, rental_rate, length, replacement_cost, rating) VALUES 
(1, 'The Matrix', 'A sci-fi classic', 1999, 1, 3, 4.99, 136, 19.99, 'R') ON DUPLICATE KEY UPDATE film_id = film_id,
(2, 'Inception', 'A mind-bending thriller', 2010, 1, 3, 4.99, 148, 24.99, 'PG-13') ON DUPLICATE KEY UPDATE film_id = film_id,
(3, 'Toy Story', 'A heartwarming animated film', 1995, 1, 3, 2.99, 81, 14.99, 'G') ON DUPLICATE KEY UPDATE film_id = film_id;

-- Insert film categories
INSERT INTO film_category (film_id, category_id) VALUES 
(1, 1) ON DUPLICATE KEY UPDATE film_id = film_id,
(2, 1) ON DUPLICATE KEY UPDATE film_id = film_id,
(3, 2) ON DUPLICATE KEY UPDATE film_id = film_id,
(3, 3) ON DUPLICATE KEY UPDATE film_id = film_id;

-- Insert inventory
INSERT INTO inventory (inventory_id, film_id, store_id) VALUES 
(1, 1, 1) ON DUPLICATE KEY UPDATE inventory_id = inventory_id,
(2, 2, 1) ON DUPLICATE KEY UPDATE inventory_id = inventory_id,
(3, 3, 1) ON DUPLICATE KEY UPDATE inventory_id = inventory_id,
(4, 1, 2) ON DUPLICATE KEY UPDATE inventory_id = inventory_id,
(5, 2, 2) ON DUPLICATE KEY UPDATE inventory_id = inventory_id;

-- Insert rentals
INSERT INTO rental (rental_id, rental_date, inventory_id, customer_id, return_date, staff_id) VALUES 
(1, DATE_SUB(NOW(), INTERVAL 5 DAY), 1, 1, DATE_SUB(NOW(), INTERVAL 2 DAY), 1) ON DUPLICATE KEY UPDATE rental_id = rental_id,
(2, DATE_SUB(NOW(), INTERVAL 3 DAY), 2, 2, DATE_SUB(NOW(), INTERVAL 1 DAY), 1) ON DUPLICATE KEY UPDATE rental_id = rental_id,
(3, DATE_SUB(NOW(), INTERVAL 1 DAY), 3, 3, NOW(), 2) ON DUPLICATE KEY UPDATE rental_id = rental_id;

-- Insert payments
INSERT INTO payment (payment_id, customer_id, staff_id, rental_id, amount, payment_date) VALUES 
(1, 1, 1, 1, 4.99, DATE_SUB(NOW(), INTERVAL 2 DAY)) ON DUPLICATE KEY UPDATE payment_id = payment_id,
(2, 2, 1, 2, 4.99, DATE_SUB(NOW(), INTERVAL 1 DAY)) ON DUPLICATE KEY UPDATE payment_id = payment_id,
(3, 3, 2, 3, 2.99, NOW()) ON DUPLICATE KEY UPDATE payment_id = payment_id;

-- Create ETL user with read-only access to source data
CREATE USER IF NOT EXISTS 'sakila'@'%' IDENTIFIED BY 'sakila';
GRANT SELECT ON sakila.* TO 'sakila'@'%';
GRANT SHOW VIEW ON sakila.* TO 'sakila'@'%';

-- Log completion
SELECT 'MySQL database initialized for sakila_dw ETL pipeline' AS message;
