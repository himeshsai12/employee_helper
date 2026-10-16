-- Select the database configured in DB_NAME before running this script.
-- This script creates tables only; it contains no employee or ticket records.

CREATE TABLE IF NOT EXISTS employees (
    employee_id VARCHAR(20) NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150),
    department VARCHAR(100),
    leave_balance INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id VARCHAR(30) NOT NULL PRIMARY KEY,
    employee_id VARCHAR(20) NOT NULL,
    issue VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS assets (
    asset_id VARCHAR(20) NOT NULL PRIMARY KEY,
    employee_id VARCHAR(20) NOT NULL,
    asset_type VARCHAR(50),
    asset_name VARCHAR(100),
    status VARCHAR(50),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conversations (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    user_message TEXT NOT NULL,
    assistant_message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX conversations_session (session_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
