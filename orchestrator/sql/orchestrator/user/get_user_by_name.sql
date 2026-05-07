SELECT
    id, username, display_name, phone_number, telegram_user_id, config, created_at, updated_at, is_admin
FROM users
WHERE LOWER(username) = LOWER(%s)
   OR LOWER(display_name) = LOWER(%s)
LIMIT 1;
