CREATE DATABASE IF NOT EXISTS desert_bloom
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE desert_bloom;

CREATE TABLE IF NOT EXISTS enquiries (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(254) NOT NULL,
    phone VARCHAR(30) NULL,
    client_type VARCHAR(100) NOT NULL,
    category VARCHAR(150) NOT NULL,
    budget VARCHAR(80) NULL,
    deadline VARCHAR(120) NULL,
    description TEXT NOT NULL,
    status ENUM('New', 'In Progress', 'Completed', 'Closed') NOT NULL DEFAULT 'New',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_enquiries_created_at (created_at),
    INDEX idx_enquiries_status (status)
) ENGINE=InnoDB;
