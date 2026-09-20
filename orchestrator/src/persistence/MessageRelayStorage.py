from __future__ import annotations

import json
from typing import Optional

from src.models.orchestrator.MessageRelay import (
    MessageRelayEndpoint,
    MessageRelayRoute,
    MessageRelayTarget,
)
from src.persistence.JobDb import JobDb


_ENDPOINT_COLUMNS = (
    "id, key, name, type, enabled, capabilities, config, created_at, updated_at"
)

_ROUTE_COLUMNS = (
    "id, key, name, enabled, match_all_sources, filter, is_preset, created_at, updated_at"
)


class MessageRelayStorage:
    """Persistence for transport-independent endpoints and routes."""

    def __init__(self):
        self._db = JobDb.instance()

    def _execute(self, query: str, params=None):
        return self._db.execute(query, params)

    def _commit(self) -> None:
        self._db.commit()

    def _rollback(self) -> None:
        self._db.rollback()

    # ── Endpoints ──────────────────────────────────────────────────────────

    def get_endpoints(self) -> list[MessageRelayEndpoint]:
        rows = self._execute(
            f"SELECT {_ENDPOINT_COLUMNS} FROM message_relay_endpoints ORDER BY name, id"
        ).fetchall()
        return [MessageRelayEndpoint.from_db_row(row) for row in rows]

    def get_endpoint(self, endpoint_id: int) -> Optional[MessageRelayEndpoint]:
        row = self._execute(
            f"SELECT {_ENDPOINT_COLUMNS} FROM message_relay_endpoints WHERE id = %s",
            (endpoint_id,),
        ).fetchone()
        return MessageRelayEndpoint.from_db_row(row) if row else None

    def save_endpoint(self, endpoint: MessageRelayEndpoint) -> MessageRelayEndpoint:
        values = (
            endpoint.key,
            endpoint.name,
            endpoint.type,
            1 if endpoint.enabled else 0,
            json.dumps(endpoint.capabilities),
            json.dumps(endpoint.config),
        )
        if endpoint.id:
            row = self._execute(
                "UPDATE message_relay_endpoints "
                "SET key = %s, name = %s, type = %s, enabled = %s, "
                "capabilities = %s, config = %s, updated_at = NOW() "
                "WHERE id = %s RETURNING " + _ENDPOINT_COLUMNS,
                values + (endpoint.id,),
            ).fetchone()
            if row is None:
                raise KeyError("Endpoint not found")
        else:
            row = self._execute(
                "INSERT INTO message_relay_endpoints "
                "(key, name, type, enabled, capabilities, config) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING " + _ENDPOINT_COLUMNS,
                values,
            ).fetchone()
        self._commit()
        return MessageRelayEndpoint.from_db_row(row)

    def delete_endpoint(self, endpoint_id: int) -> bool:
        row = self._execute(
            "DELETE FROM message_relay_endpoints WHERE id = %s RETURNING id",
            (endpoint_id,),
        ).fetchone()
        self._commit()
        return row is not None

    # ── Routes ─────────────────────────────────────────────────────────────

    def get_routes(self) -> list[MessageRelayRoute]:
        rows = self._execute(
            f"SELECT {_ROUTE_COLUMNS} FROM message_relay_routes ORDER BY name, id"
        ).fetchall()
        routes = [MessageRelayRoute.from_db_row(row) for row in rows]
        if not routes:
            return routes

        endpoints = {endpoint.id: endpoint for endpoint in self.get_endpoints()}
        route_map = {route.id: route for route in routes}

        source_rows = self._execute(
            "SELECT route_id, endpoint_id FROM message_relay_route_sources "
            "ORDER BY route_id, endpoint_id"
        ).fetchall()
        for route_id, endpoint_id in source_rows:
            route = route_map.get(int(route_id))
            endpoint = endpoints.get(int(endpoint_id))
            if route is not None and endpoint is not None:
                route.sources.append(endpoint)

        target_rows = self._execute(
            "SELECT route_id, endpoint_id, enabled, transform "
            "FROM message_relay_route_targets ORDER BY route_id, endpoint_id"
        ).fetchall()
        for route_id, endpoint_id, enabled, transform in target_rows:
            route = route_map.get(int(route_id))
            endpoint = endpoints.get(int(endpoint_id))
            if route is not None and endpoint is not None:
                if isinstance(transform, str):
                    transform = json.loads(transform)
                route.targets.append(MessageRelayTarget(
                    endpoint=endpoint,
                    enabled=bool(enabled),
                    transform=transform or {},
                ))
        return routes

    def get_route(self, route_id: int) -> Optional[MessageRelayRoute]:
        return next((route for route in self.get_routes() if route.id == route_id), None)

    def get_route_by_key(self, key: str) -> Optional[MessageRelayRoute]:
        return next((route for route in self.get_routes() if route.key == key), None)

    def save_route(self, route: MessageRelayRoute) -> MessageRelayRoute:
        values = (
            route.key,
            route.name,
            1 if route.enabled else 0,
            1 if route.match_all_sources else 0,
            json.dumps(route.filter) if route.filter is not None else None,
            1 if route.is_preset else 0,
        )
        try:
            if route.id:
                row = self._execute(
                    "UPDATE message_relay_routes "
                    "SET key = %s, name = %s, enabled = %s, match_all_sources = %s, "
                    "filter = %s, is_preset = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING " + _ROUTE_COLUMNS,
                    values + (route.id,),
                ).fetchone()
                if row is None:
                    raise KeyError("Route not found")
                route_id = int(row[0])
                self._execute("DELETE FROM message_relay_route_sources WHERE route_id = %s", (route_id,))
                self._execute("DELETE FROM message_relay_route_targets WHERE route_id = %s", (route_id,))
            else:
                row = self._execute(
                    "INSERT INTO message_relay_routes "
                    "(key, name, enabled, match_all_sources, filter, is_preset) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING " + _ROUTE_COLUMNS,
                    values,
                ).fetchone()
                route_id = int(row[0])

            if not route.match_all_sources:
                for endpoint_id in dict.fromkeys(route.source_endpoint_ids):
                    self._execute(
                        "INSERT INTO message_relay_route_sources (route_id, endpoint_id) VALUES (%s, %s)",
                        (route_id, endpoint_id),
                    )

            seen_targets: set[int] = set()
            for target in route.target_specs:
                endpoint_id = int(target.get("endpoint_id") or 0)
                if not endpoint_id or endpoint_id in seen_targets:
                    continue
                seen_targets.add(endpoint_id)
                self._execute(
                    "INSERT INTO message_relay_route_targets "
                    "(route_id, endpoint_id, enabled, transform) VALUES (%s, %s, %s, %s)",
                    (
                        route_id,
                        endpoint_id,
                        1 if target.get("enabled", True) else 0,
                        json.dumps(target.get("transform") or {}),
                    ),
                )
            self._commit()
        except Exception:
            self._rollback()
            raise

        saved = self.get_route(route_id)
        if saved is None:
            raise RuntimeError("Saved route could not be reloaded")
        return saved

    def set_route_enabled(self, key: str, enabled: bool) -> Optional[MessageRelayRoute]:
        row = self._execute(
            "UPDATE message_relay_routes SET enabled = %s, updated_at = NOW() "
            "WHERE key = %s RETURNING id",
            (1 if enabled else 0, key),
        ).fetchone()
        self._commit()
        return self.get_route(int(row[0])) if row else None

    def set_target_enabled(
        self, route_key: str, endpoint_key: str, enabled: bool
    ) -> Optional[MessageRelayRoute]:
        row = self._execute(
            "UPDATE message_relay_route_targets target "
            "SET enabled = %s "
            "FROM message_relay_routes route, message_relay_endpoints endpoint "
            "WHERE target.route_id = route.id AND target.endpoint_id = endpoint.id "
            "AND route.key = %s AND endpoint.key = %s RETURNING target.route_id",
            (1 if enabled else 0, route_key, endpoint_key),
        ).fetchone()
        self._commit()
        return self.get_route(int(row[0])) if row else None

    def set_preset_enabled(self, enabled: bool) -> None:
        self._execute(
            "UPDATE message_relay_routes SET enabled = %s, updated_at = NOW() WHERE is_preset = 1",
            (1 if enabled else 0,),
        )
        self._commit()

    def delete_route(self, route_id: int) -> bool:
        row = self._execute(
            "DELETE FROM message_relay_routes WHERE id = %s RETURNING id",
            (route_id,),
        ).fetchone()
        self._commit()
        return row is not None
