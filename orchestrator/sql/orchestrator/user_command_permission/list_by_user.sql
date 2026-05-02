SELECT command_path
FROM user_command_permissions
WHERE user_id = %s
ORDER BY command_path;
