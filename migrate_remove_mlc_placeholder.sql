-- Migration: remove the MLC league-placeholder team row.
--
-- Background: info-teams.csv contains league-placeholder rows whose
-- real_team_name matches the league's full name (e.g. "Major League Cricket").
-- import_data_modular.py:261-264 filters those out before insert. Earlier
-- import scripts (import_data.py, import_data_updated.py) do NOT, so an MLC
-- placeholder row got into prod via an earlier run and never got cleaned up.
--
-- Symptom on /admin: 186 teams total, 185 linked → 1 unlinked, surfaced via
-- /teams?linked=false as the MLC entry.
--
-- This migration deletes that one row, with a safety check that aborts if
-- the number of matching rows is anything other than 1.

BEGIN;

DO $$
DECLARE
    target_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO target_count
    FROM teams
    WHERE stadium_id IS NULL
      AND league_id = (SELECT league_id FROM leagues WHERE league_name_proper = 'MLC');

    IF target_count <> 1 THEN
        RAISE EXCEPTION
            'Aborting: expected exactly 1 unlinked MLC team, found %. Inspect /teams?linked=false before re-running.',
            target_count;
    END IF;
END $$;

DELETE FROM teams
WHERE stadium_id IS NULL
  AND league_id = (SELECT league_id FROM leagues WHERE league_name_proper = 'MLC');

COMMIT;
