CREATE TABLE user_command_permissions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    command_path VARCHAR(100) NOT NULL,
    CONSTRAINT ucp_user_command_unique UNIQUE (user_id, command_path),
    CONSTRAINT ucp_user_fk FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
