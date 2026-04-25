-- Add CV item type and database-backed attachment storage

INSERT OR IGNORE INTO item_types (id, name) VALUES
    (7, 'cv');

INSERT OR IGNORE INTO type_status_workflow (type_id, status_id, sequence) VALUES
    (7, 1, 1),
    (7, 2, 2),
    (7, 3, 3),
    (7, 4, 4),
    (7, 5, 5),
    (7, 6, 6),
    (7, 7, 7);

CREATE TABLE IF NOT EXISTS item_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    mime_type TEXT DEFAULT NULL,
    file_data BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now')),
    UNIQUE (item_id, file_name),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);