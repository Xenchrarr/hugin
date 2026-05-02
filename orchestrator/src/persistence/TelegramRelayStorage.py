from __future__ import annotations

import json
from typing import Optional

from src.models.orchestrator.TelegramRelay import TelegramRelayDestination, TelegramRelayRule
from src.persistence.JobDb import JobDb
from src.persistence.Database import read_sql_file


class TelegramRelayStorage:

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

    # ── Destinations ──────────────────────────────────────────

    def get_destinations(self) -> list[TelegramRelayDestination]:
        query = read_sql_file('orchestrator/telegram_relay/get_destinations.sql')
        self.execute(query)
        return [TelegramRelayDestination.from_db_row(row) for row in self.fetchall()]

    def get_destination(self, destination_id: int) -> Optional[TelegramRelayDestination]:
        query = read_sql_file('orchestrator/telegram_relay/get_destination.sql')
        self.execute(query, (destination_id,))
        row = self.fetchone()
        return TelegramRelayDestination.from_db_row(row) if row else None

    def create_destination(self, dest: TelegramRelayDestination) -> TelegramRelayDestination:
        query = read_sql_file('orchestrator/telegram_relay/create_destination.sql')
        self.execute(
            query,
            (
                dest.name,
                dest.type,
                json.dumps(dest.config),
                1 if dest.enabled else 0,
            ),
        )
        row = self.fetchone()
        self.commit()
        return TelegramRelayDestination.from_db_row(row)

    def update_destination(self, dest: TelegramRelayDestination) -> Optional[TelegramRelayDestination]:
        query = read_sql_file('orchestrator/telegram_relay/update_destination.sql')
        self.execute(
            query,
            (
                dest.name,
                dest.type,
                json.dumps(dest.config),
                1 if dest.enabled else 0,
                dest.id,
            ),
        )
        row = self.fetchone()
        self.commit()
        return TelegramRelayDestination.from_db_row(row) if row else None

    def delete_destination(self, destination_id: int) -> None:
        query = read_sql_file('orchestrator/telegram_relay/delete_destination.sql')
        self.execute(query, (destination_id,))
        self.commit()

    # ── Rules ─────────────────────────────────────────────────

    def get_rules(self) -> list[TelegramRelayRule]:
        query = read_sql_file('orchestrator/telegram_relay/get_rules.sql')
        self.execute(query)
        return [TelegramRelayRule.from_db_row(row) for row in self.fetchall()]

    def get_rule(self, rule_id: int) -> Optional[TelegramRelayRule]:
        query = read_sql_file('orchestrator/telegram_relay/get_rule.sql')
        self.execute(query, (rule_id,))
        row = self.fetchone()
        return TelegramRelayRule.from_db_row(row) if row else None

    def create_rule(self, rule: TelegramRelayRule) -> TelegramRelayRule:
        query = read_sql_file('orchestrator/telegram_relay/create_rule.sql')
        self.execute(
            query,
            (
                rule.name,
                rule.priority,
                1 if rule.enabled else 0,
                1 if rule.continue_on_match else 0,
                json.dumps(rule.conditions) if rule.conditions is not None else None,
                json.dumps(rule.actions),
            ),
        )
        row = self.fetchone()
        self.commit()
        return TelegramRelayRule.from_db_row(row)

    def update_rule(self, rule: TelegramRelayRule) -> Optional[TelegramRelayRule]:
        query = read_sql_file('orchestrator/telegram_relay/update_rule.sql')
        self.execute(
            query,
            (
                rule.name,
                rule.priority,
                1 if rule.enabled else 0,
                1 if rule.continue_on_match else 0,
                json.dumps(rule.conditions) if rule.conditions is not None else None,
                json.dumps(rule.actions),
                rule.id,
            ),
        )
        row = self.fetchone()
        self.commit()
        return TelegramRelayRule.from_db_row(row) if row else None

    def delete_rule(self, rule_id: int) -> None:
        query = read_sql_file('orchestrator/telegram_relay/delete_rule.sql')
        self.execute(query, (rule_id,))
        self.commit()
