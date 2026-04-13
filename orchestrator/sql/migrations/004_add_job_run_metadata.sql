-- Add metadata JSONB column to job_runs for analytics-friendly tags
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Backfill metadata for existing run_script rows from the parameter JSON
UPDATE job_runs
SET metadata = jsonb_build_object(
    'ControlRoom', parameter::jsonb ->> 'ControlRoom',
    'script_name', parameter::jsonb ->> 'script_name'
)
WHERE job_type = 'run_script'
  AND parameter IS NOT NULL
  AND parameter != ''
  AND parameter != '0'
  AND parameter LIKE '{%';
