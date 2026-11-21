# What the CLI needs from the rest of the project

A proposal from Adil (CLI). It lists every table, setting and function the CLI will use, so we can build our parts at the same time. If something doesn't suit your part, change it and tell me, and the CLI will follow.

## Database (PostgreSQL on Neon)

Tables and columns exactly as in the ERD in `REQUIRENTS.md`: `patient`, `patient_identity`, `recording`, `seizure_annotation`.

The CLI relies on:
- `patient.patient_id` and `recording.recording_id` being created by the database (e.g. `GENERATED ALWAYS AS IDENTITY`).
- `recording.sha256` being `UNIQUE`, so the same .edf file can't be added twice.
- `seizure_annotation.recording_id` having `ON DELETE CASCADE`, so removing a recording removes its seizures.
- The personal columns of `patient_identity` being `bytea`, encrypted with pgcrypto: `pgp_sym_encrypt(value, key)`. The CLI sends the key with each query, taken from the user's `TDM_DATA_KEY` environment variable. The key is never stored in the database or the repo.
- The SQL being saved in the repo as numbered files in `sql/` (`01_create.sql`, `02_roles.sql`, ...), not only typed into the Neon console. The automated tests run those files to build the same database locally, and the rubric asks for the scripts anyway.

### Users and roles
- Three group roles that can't log in, `admin`, `medical_user` and `developer`, with the privileges from the table in `REQUIRENTS.md`.
- Each person is their own login role and a member of exactly one group. After login, the CLI asks PostgreSQL which group the person is in.
- People are created with SQL (`CREATE ROLE`), not in the Neon console. Users made in the console join `neon_superuser` and get near-admin powers, which would break the developer restrictions.

### Managing users (done: `sql/03_user_management.sql`)
Since PostgreSQL 16 (Neon runs 18), `CREATEROLE` is not inherited from a group. An admin can only put people into `developer` etc. if they hold that group `WITH ADMIN OPTION`, and can only drop users they created themselves.

So `sql/03_user_management.sql` adds three small `SECURITY DEFINER` functions, `create_user(name, password, group)`, `drop_user(name)` and `change_group(name, group)`, with `EXECUTE` granted only to `admin`. They run with the rights of the database owner, only accept the three groups, and refuse to touch the owner, superusers or the caller's own account. PostgreSQL still decides who may manage users, and any admin can manage anyone. The CLI's `adduser`, `removeuser` and `setgroup` call them.

What the roles script needs for this:
- Create the three groups while logged in as `neondb_owner`. The owner then automatically gets `ADMIN OPTION` on them, which the functions need.
- Then run `sql/03_user_management.sql`, also as `neondb_owner`. For example, log in to `tdm` as `neondb_owner` and type `script sql/03_user_management.sql`.
- Make the first admin the same way: as `neondb_owner`, type `adduser <name> admin`.
- Neon only accepts passwords in plain text in `CREATE ROLE` / `ALTER ROLE` (it hashes them itself), so don't pre-hash them.

## Converting .edf files (Python)

These can be methods of `DataProcessor` in `src/DataProcessing.py`.

| Function | Returns / does |
|---|---|
| `edf_info(edf_path) -> dict` | `{"duration_s": float, "sample_rate_hz": int, "n_channels": int}` |
| `edf_seizures(edf_path) -> list[tuple[float, float]]` | `(start_s, end_s)` of each seizure in that recording |
| `append_recording(edf_path, parquet_path, patient_id, recording_id) -> None` | Adds the signal (float16) to the patient's parquet file, tagged with both IDs. Creates the file if it doesn't exist yet. |
| `remove_recording(parquet_path, recording_id) -> None` | Removes that recording's rows from the file |

## Hugging Face (Python)

Any module name you like. The access token is read from the `HF_TOKEN` environment variable.

| Function | Returns / does |
|---|---|
| `download_raw(patient_id, dest_dir) -> Path \| None` | Downloads `raw_signals/patient_<id>.parquet`. Returns `None` if the patient has no file yet. |
| `upload_raw(patient_id, path) -> None` | Uploads (replaces) that file |
| `upload_npy(path, patient_id) -> None` | Uploads `Processed_signals/patient_<id>.npy` |
| `delete_npy(patient_id) -> None` | Deletes it |
| `download_signals(dest_dir) -> None` | Downloads all raw and processed signal files |

## Until these exist

The CLI uses stand-ins: placeholder tables in the local test database, and a local folder instead of Hugging Face. When your version lands, the CLI switches to it.
