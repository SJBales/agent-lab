-- One active steering note per patient. The therapist writes free-text
-- guidance that gets appended to the companion's system prompt for all
-- future chat turns. Updating overwrites the previous guidance.
CREATE TABLE IF NOT EXISTS patient_steering (
    patient_id INT PRIMARY KEY,
    guidance   TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
