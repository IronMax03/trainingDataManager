-- User management for the CLI commands adduser, removeuser and setgroup.
--
-- Since PostgreSQL 16, being in the admin group is not enough to create users or move them between
-- groups. So these three functions run with the rights of the database owner who creates them
-- (SECURITY DEFINER), and only members of admin are allowed to call them.
--
-- Run this file as the database owner (neondb_owner on Neon), after the groups admin, medical_user
-- and developer exist. With the CLI: log in as neondb_owner and type  script sql/03_user_management.sql
-- Running it again is safe.


-- create_user('bob', 'his password', 'developer')
CREATE OR REPLACE FUNCTION public.create_user(user_name text, password text, group_name text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp     -- so nobody can slip in their own version of a function used here
SET password_encryption = 'scram-sha-256' -- PostgreSQL keeps only a strong hash of the password
AS $$
BEGIN
    IF group_name NOT IN ('admin', 'medical_user', 'developer') THEN
        RAISE EXCEPTION 'Unknown group "%": use admin, medical_user or developer.', group_name;
    END IF;
    -- %I quotes a name and %L a value, so nothing typed by the user can run as SQL
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L IN ROLE %I', user_name, password, group_name);
EXCEPTION WHEN OTHERS THEN
    -- Report only the error: by default it would quote the CREATE ROLE line, password included
    RAISE EXCEPTION USING ERRCODE = SQLSTATE, MESSAGE = SQLERRM;
END
$$;


-- drop_user('bob')
CREATE OR REPLACE FUNCTION public.drop_user(user_name text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF user_name = session_user THEN
        RAISE EXCEPTION 'You can''t remove your own account: ask another admin.';
    END IF;

    -- Only people in one of the three groups, never the database owner or other special roles
    IF NOT EXISTS (
        SELECT FROM pg_roles u
            JOIN pg_auth_members m ON m.member = u.oid
            JOIN pg_roles g ON g.oid = m.roleid
        WHERE u.rolname = user_name AND u.rolcanlogin AND NOT u.rolsuper AND NOT u.rolcreaterole
            AND g.rolname IN ('admin', 'medical_user', 'developer')
    ) THEN
        RAISE EXCEPTION 'There is no user called "%".', user_name;
    END IF;

    EXECUTE format('DROP ROLE %I', user_name);
END
$$;


-- change_group('bob', 'medical_user')
CREATE OR REPLACE FUNCTION public.change_group(user_name text, group_name text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    user_id oid;
    old_group text;
    given_by text;
BEGIN
    IF group_name NOT IN ('admin', 'medical_user', 'developer') THEN
        RAISE EXCEPTION 'Unknown group "%": use admin, medical_user or developer.', group_name;
    END IF;

    IF user_name = session_user THEN
        RAISE EXCEPTION 'You can''t change your own group: ask another admin.';
    END IF;

    SELECT u.oid INTO user_id FROM pg_roles u
        JOIN pg_auth_members m ON m.member = u.oid
        JOIN pg_roles g ON g.oid = m.roleid
    WHERE u.rolname = user_name AND u.rolcanlogin AND NOT u.rolsuper AND NOT u.rolcreaterole
        AND g.rolname IN ('admin', 'medical_user', 'developer')
    LIMIT 1;
    IF user_id IS NULL THEN
        RAISE EXCEPTION 'There is no user called "%".', user_name;
    END IF;

    -- Leave the old group(s), then join the new one: each user is in exactly one group
    FOR old_group IN
        SELECT DISTINCT g.rolname FROM pg_auth_members m JOIN pg_roles g ON g.oid = m.roleid
        WHERE m.member = user_id AND g.rolname IN ('admin', 'medical_user', 'developer')
            AND g.rolname <> group_name
    LOOP
        EXECUTE format('REVOKE %I FROM %I', old_group, user_name);
    END LOOP;

    -- REVOKE only removes what the owner itself granted. If someone else put the user in a group,
    -- they are still in it: stop, and undo everything, instead of leaving them in two groups.
    SELECT g.rolname, m.grantor::regrole::text INTO old_group, given_by
    FROM pg_auth_members m JOIN pg_roles g ON g.oid = m.roleid
    WHERE m.member = user_id AND g.rolname IN ('admin', 'medical_user', 'developer')
        AND g.rolname <> group_name
    LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'Can''t take "%" out of %: % put them there, not the database owner.',
            user_name, old_group, given_by;
    END IF;

    IF NOT EXISTS (
        SELECT FROM pg_auth_members m JOIN pg_roles g ON g.oid = m.roleid
        WHERE m.member = user_id AND g.rolname = group_name
    ) THEN
        EXECUTE format('GRANT %I TO %I', group_name, user_name);
    END IF;
END
$$;


-- By default everyone may call a new function: only admin may call these
REVOKE ALL ON FUNCTION public.create_user(text, text, text), public.drop_user(text), public.change_group(text, text)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.create_user(text, text, text), public.drop_user(text), public.change_group(text, text)
    TO admin;
