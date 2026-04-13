SELECT script_name
FROM script_permissions
WHERE allowed_for_servicedesk = TRUE
ORDER BY script_name;
