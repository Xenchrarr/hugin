UPDATE users
SET password_hash = %s,
    updated_at    = NOW()
WHERE id = %s
RETURNING id, username, display_name, phone_number, telegram_user_id, config, created_at, updated_at, is_admin;
