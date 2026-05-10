-- Create sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    patient_id  INT NOT NULL,
    title       TEXT,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ
);

-- Add session_id to messages (nullable so existing rows can be backfilled)
ALTER TABLE messages ADD COLUMN IF NOT EXISTS session_id INT;

-- Backfill: bucket all pre-existing messages for each patient into one
-- "legacy" session so we can flip session_id to NOT NULL.
INSERT INTO sessions (patient_id, title, started_at)
SELECT patient_id, 'Legacy session', MIN(created_at)
FROM messages
WHERE session_id IS NULL
GROUP BY patient_id;

UPDATE messages m
SET session_id = s.id
FROM sessions s
WHERE m.session_id IS NULL
  AND s.patient_id = m.patient_id
  AND s.title = 'Legacy session';

-- Enforce NOT NULL + FK + index for session-scoped queries
ALTER TABLE messages ALTER COLUMN session_id SET NOT NULL;

ALTER TABLE messages
    DROP CONSTRAINT IF EXISTS messages_session_id_fkey;
ALTER TABLE messages
    ADD CONSTRAINT messages_session_id_fkey
    FOREIGN KEY (session_id) REFERENCES sessions(id);

CREATE INDEX IF NOT EXISTS messages_session_id_id_idx
    ON messages (session_id, id);
