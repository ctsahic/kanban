-- Add CV item type and database-backed attachment storage

INSERT IGNORE INTO item_types (id, name) VALUES
    (7, 'cv');

INSERT IGNORE INTO type_status_workflow (type_id, status_id, sequence) VALUES
    (7, 1, 1),
    (7, 2, 2),
    (7, 3, 3),
    (7, 4, 4),
    (7, 5, 5),
    (7, 6, 6);

CREATE TABLE IF NOT EXISTS item_attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) DEFAULT NULL,
    file_data LONGBLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_item_attachment (item_id, file_name),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;