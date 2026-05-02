INSERT INTO user_command_permissions (user_id, command_path)
VALUES (%s, %s)
ON CONFLICT (user_id, command_path) DO NOTHING;
