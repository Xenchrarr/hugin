SELECT original_filename, download_url, uploaded_at, step_run_id
FROM job_run_files WHERE job_run_id = %s ORDER BY uploaded_at, id;
