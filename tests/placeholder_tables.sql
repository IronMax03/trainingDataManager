-- Stand-ins for the patient tables, used by the tests until the real ones are in sql/
-- (same columns as the ERD in REQUIRENTS.md). Replace them with the real file when it exists.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE patient (
    patient_id    int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sex           char(1) NOT NULL CHECK (sex IN ('F', 'M', 'U')),
    raw_file_path text   -- set when the first recording is added
);

CREATE TABLE patient_identity (
    patient_id      int PRIMARY KEY REFERENCES patient ON DELETE CASCADE,
    name_enc        bytea NOT NULL,
    address_enc     bytea,
    birth_date_enc  bytea,
    hospital_no_enc bytea
);

GRANT SELECT, INSERT, UPDATE ON patient, patient_identity TO admin, medical_user;
GRANT SELECT ON patient TO developer;   -- and nothing at all on patient_identity
