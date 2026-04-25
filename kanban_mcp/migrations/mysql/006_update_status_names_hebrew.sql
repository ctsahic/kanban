-- Migration: Update status names to Hebrew
-- Changes from: backlog, todo, in_progress, review, done, closed
-- Changes to: חדשים, ראיון טלפוני, ראיון מקצועי, רותם, שכר, סיווג

UPDATE statuses SET name = 'חדשים' WHERE name = 'backlog';
UPDATE statuses SET name = 'ראיון טלפוני' WHERE name = 'todo';
UPDATE statuses SET name = 'ראיון מקצועי' WHERE name = 'in_progress';
UPDATE statuses SET name = 'רותם' WHERE name = 'review';
UPDATE statuses SET name = 'שכר' WHERE name = 'done';
UPDATE statuses SET name = 'סיווג' WHERE name = 'closed';


