-- Migration: Initial schema for kanban-mcp
-- Run with: mysql -u kanban -p kanban < migrations/001_initial_schema.sql
--
-- Prerequisites:
--   CREATE DATABASE kanban CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
--   CREATE USER 'kanban'@'localhost' IDENTIFIED BY 'changeme';
--   GRANT ALL PRIVILEGES ON kanban.* TO 'kanban'@'localhost';

-- ============================================================
-- Lookup tables
-- ============================================================

CREATE TABLE IF NOT EXISTS item_types (
    id TINYINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(20) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS statuses (
    id TINYINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(30) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS type_status_workflow (
    type_id TINYINT NOT NULL,
    status_id TINYINT NOT NULL,
    sequence TINYINT NOT NULL,
    PRIMARY KEY (type_id, status_id),
    FOREIGN KEY (type_id) REFERENCES item_types(id),
    FOREIGN KEY (status_id) REFERENCES statuses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Core tables
-- ============================================================

CREATE TABLE IF NOT EXISTS projects (
    id CHAR(16) NOT NULL PRIMARY KEY,
    directory_path VARCHAR(500) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id CHAR(16) NOT NULL,
    type_id TINYINT NOT NULL,
    status_id TINYINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority TINYINT DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    closed_at TIMESTAMP NULL DEFAULT NULL,
    complexity TINYINT DEFAULT NULL,
    parent_id INT DEFAULT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (type_id) REFERENCES item_types(id),
    FOREIGN KEY (status_id) REFERENCES statuses(id),
    FOREIGN KEY (parent_id) REFERENCES items(id) ON DELETE CASCADE,
    INDEX idx_project_status (project_id, status_id),
    INDEX idx_type_status (type_id, status_id),
    INDEX idx_items_parent_id (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS updates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id CHAR(16) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    INDEX idx_project_created (project_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS update_items (
    update_id INT NOT NULL,
    item_id INT NOT NULL,
    PRIMARY KEY (update_id, item_id),
    FOREIGN KEY (update_id) REFERENCES updates(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS item_relationships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_item_id INT NOT NULL,
    target_item_id INT NOT NULL,
    relationship_type ENUM('blocks', 'depends_on', 'relates_to', 'duplicates') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_relationship (source_item_id, target_item_id, relationship_type),
    FOREIGN KEY (source_item_id) REFERENCES items(id) ON DELETE CASCADE,
    FOREIGN KEY (target_item_id) REFERENCES items(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(16) NOT NULL,
    name VARCHAR(50) NOT NULL,
    color VARCHAR(7) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_tag_per_project (project_id, name),
    INDEX idx_project_tags (project_id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS item_tags (
    item_id INT NOT NULL,
    tag_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (item_id, tag_id),
    INDEX idx_tag_items (tag_id),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS item_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    line_start INT DEFAULT NULL,
    line_end INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_item_file_lines (item_id, file_path, line_start, line_end),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS item_decisions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    choice VARCHAR(200) NOT NULL,
    rejected_alternatives VARCHAR(500) DEFAULT NULL,
    rationale VARCHAR(200) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_item_decisions_item (item_id),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS status_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    old_status_id TINYINT DEFAULT NULL,
    new_status_id TINYINT NOT NULL,
    change_type ENUM('create', 'advance', 'revert', 'set', 'close', 'auto_advance') NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_item_changed (item_id, changed_at),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    FOREIGN KEY (old_status_id) REFERENCES statuses(id),
    FOREIGN KEY (new_status_id) REFERENCES statuses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Seed data
-- ============================================================

INSERT INTO item_types (id, name) VALUES
    (7, 'cv');

INSERT INTO statuses (id, name) VALUES
    (1, 'backlog'),
    (2, 'todo'),
    (3, 'in_progress'),
    (4, 'review'),
    (5, 'done'),
    (6, 'closed');

-- Workflow: which statuses are valid for each type, and in what order
INSERT INTO type_status_workflow (type_id, status_id, sequence) VALUES
    -- cv: backlog → todo → in_progress → review → done → closed
    (7, 1, 1), (7, 2, 2), (7, 3, 3), (7, 4, 4), (7, 5, 5), (7, 6, 6);
