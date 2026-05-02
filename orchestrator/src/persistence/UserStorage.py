from __future__ import annotations

import json
from typing import Optional

from src.models.orchestrator.User import User
from src.persistence.JobDb import JobDb
from src.persistence.Database import read_sql_file


class UserStorage:

    def __init__(self):
        self._db = JobDb.instance()

    def execute(self, query: str, params=None):
        self._last_cursor = self._db.execute(query, params)

    def fetchall(self):
        return self._last_cursor.fetchall()

    def fetchone(self):
        return self._last_cursor.fetchone()

    def commit(self):
        self._db.commit()

    def list_users(self) -> list[User]:
        query = read_sql_file('orchestrator/user/list_users.sql')
        self.execute(query)
        return [User.from_db_row(row) for row in self.fetchall()]

    def get_user(self, user_id: int) -> Optional[User]:
        query = read_sql_file('orchestrator/user/get_user.sql')
        self.execute(query, (user_id,))
        row = self.fetchone()
        return User.from_db_row(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Returns user including password_hash for authentication."""
        query = read_sql_file('orchestrator/user/get_user_by_username.sql')
        self.execute(query, (username,))
        row = self.fetchone()
        return User.from_db_row_auth(row) if row else None

    def create_user(self, user: User, password_hash: str) -> User:
        query = read_sql_file('orchestrator/user/create_user.sql')
        config_json = json.dumps(user.config) if isinstance(user.config, dict) else user.config
        self.execute(query, (
            user.username,
            user.display_name,
            user.phone_number,
            user.telegram_user_id,
            password_hash,
            config_json,            user.is_admin,        ))
        row = self.fetchone()
        self.commit()
        return User.from_db_row(row)

    def update_user(self, user: User) -> Optional[User]:
        query = read_sql_file('orchestrator/user/update_user.sql')
        config_json = json.dumps(user.config) if isinstance(user.config, dict) else user.config
        self.execute(query, (
            user.display_name,
            user.phone_number,
            user.telegram_user_id,
            config_json,            user.is_admin,            user.id,
        ))
        row = self.fetchone()
        self.commit()
        return User.from_db_row(row) if row else None

    def update_password(self, user_id: int, password_hash: str) -> Optional[User]:
        query = read_sql_file('orchestrator/user/update_user_password.sql')
        self.execute(query, (password_hash, user_id))
        row = self.fetchone()
        self.commit()
        return User.from_db_row(row) if row else None

    def delete_user(self, user_id: int) -> bool:
        query = read_sql_file('orchestrator/user/delete_user.sql')
        self.execute(query, (user_id,))
        row = self.fetchone()
        self.commit()
        return row is not None

    def lookup_user_by_channel(self, channel: str, identifier: str) -> Optional[User]:
        """Resolve a user from their phone number (sms) or telegram chat ID (telegram)."""
        if channel == 'sms':
            query = read_sql_file('orchestrator/user/lookup_by_phone.sql')
            self.execute(query, (identifier,))
        elif channel == 'telegram':
            query = read_sql_file('orchestrator/user/lookup_by_telegram.sql')
            try:
                self.execute(query, (int(identifier),))
            except (ValueError, TypeError):
                return None
        else:
            return None

        row = self.fetchone()
        return User.from_db_row(row) if row else None
