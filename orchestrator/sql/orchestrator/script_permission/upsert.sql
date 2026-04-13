INSERT INTO script_permissions (script_name, allowed_for_servicedesk, created, updated)
VALUES (%s, %s, NOW(), NOW())
ON CONFLICT (script_name) DO UPDATE
    SET allowed_for_servicedesk = EXCLUDED.allowed_for_servicedesk,
        updated = NOW();
