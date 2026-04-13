SELECT
    id,
    job_run_id,
    area,
    request_data,
    request_type,
    created,
    response_code,
    response,
    function_name,
    api_name,
    description
FROM request_log
WHERE job_run_id = %s
ORDER BY created ASC
OFFSET %s
LIMIT %s;