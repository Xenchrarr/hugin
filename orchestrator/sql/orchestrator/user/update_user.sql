UPDATE users
SET display_name      = %s,
    phone_number      = %s,
    telegram_user_id  = %s,
    config            = %s,
    is_admin          = %s,
    updated_at        = NOW()
WHERE id = %s
RETURNING id, username, display_name, phone_number, telegram_user_id, config, created_at, updated_at, is_admin;
