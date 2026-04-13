INSERT INTO request_log (
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
)
VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s);