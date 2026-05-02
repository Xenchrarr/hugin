DELETE FROM user_command_permissions
WHERE user_id = %s AND command_path = %s;
