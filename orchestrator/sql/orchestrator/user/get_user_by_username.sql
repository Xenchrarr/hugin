SELECT
    id, username, display_name, phone_number, telegram_user_id, config, created_at, updated_at,
    is_admin, password_hash
FROM users
WHERE username = %s;
