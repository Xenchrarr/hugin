INSERT INTO users (username, display_name, phone_number, telegram_user_id, password_hash, config, is_admin)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id, username, display_name, phone_number, telegram_user_id, config, created_at, updated_at, is_admin;
