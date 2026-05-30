-- Normalize the database so CV is the only item type.

INSERT IGNORE INTO item_types (id, name) VALUES
    (7, 'cv');

UPDATE items
SET type_id = 7
WHERE type_id != 7;

DELETE FROM type_status_workflow
WHERE type_id != 7;

DELETE FROM item_types
WHERE name != 'cv';

INSERT IGNORE INTO type_status_workflow (type_id, status_id, sequence) VALUES
    (7, 1, 1),
    (7, 2, 2),
    (7, 3, 3),
    (7, 4, 4),
    (7, 5, 5),
    (7, 6, 6);