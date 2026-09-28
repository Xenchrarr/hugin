import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask


# Avoid executing src/__init__.py, which boots the full application.
src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.controllers.message_hub_controller import message_hub_blueprint


class _FakeMessageHubService:
    def __init__(self):
        self.bulk_updates = []
        self.bulk_audits = []
        self.delivery_searches = []
        self.group_searches = []
        self.group_updates = []
        self.filtered_updates = []
        self.operations = [{
            "id": 7, "action": "cancel", "status": "completed",
            "affected_count": 2, "can_undo": True, "can_resume": False,
        }]
        self.undo_calls = []
        self.resume_calls = []

    def bulk_update_deliveries(self, delivery_ids, action, **audit):
        self.bulk_updates.append((delivery_ids, action))
        self.bulk_audits.append(audit)
        return {
            "requested": len(delivery_ids),
            "updated": len(delivery_ids),
            "updated_ids": delivery_ids,
            "skipped": [],
        }

    def search_deliveries(self, **filters):
        self.delivery_searches.append(filters)
        return {"items": [], "total": 0, "page": filters["page"], "page_size": filters["page_size"]}

    def search_delivery_groups(self, **filters):
        self.group_searches.append(filters)
        return {"items": [], "total": 0, "page": filters["page"], "page_size": filters["page_size"]}

    def bulk_update_delivery_group(self, **group):
        self.group_updates.append(group)
        return {
            "requested": 2, "updated": 2, "updated_ids": [1, 2], "skipped": [],
            "matching": 2, "truncated": False,
        }

    def bulk_update_matching_deliveries(self, **filters):
        self.filtered_updates.append(filters)
        return {
            "requested": 2, "updated": 2, "updated_ids": [1, 2], "skipped": [],
            "matching": 2, "remaining": 0, "truncated": False,
        }

    def get_bulk_operations(self, limit):
        return self.operations[:limit]

    def undo_bulk_operation(self, operation_id):
        self.undo_calls.append(operation_id)
        return {"operation": self.operations[0], "restored": 2, "restored_ids": [1, 2], "skipped": 0}

    def resume_bulk_operation(self, operation_id):
        self.resume_calls.append(operation_id)
        return {
            "requested": 1, "updated": 1, "updated_ids": [3], "skipped": [],
            "matching": 1, "remaining": 0, "truncated": False,
            "operation": self.operations[0],
        }

    def get_delivery_details(self, delivery_id):
        if delivery_id == 404:
            return None
        return {
            "delivery": {"id": delivery_id, "status": "held"},
            "message": {"id": 20},
            "attachments": [],
            "attempts": [],
        }


class MessageHubControllerTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(message_hub_blueprint, url_prefix="/message-hub")
        self.client = app.test_client()
        self.service = _FakeMessageHubService()
        self.auth_patch = patch(
            "src.auth.decode_token",
            return_value={"sub": "3", "username": "alice", "is_admin": True},
        )
        self.service_patch = patch(
            "src.controllers.message_hub_controller.MessageHubService.instance",
            return_value=self.service,
        )
        self.auth_patch.start()
        self.service_patch.start()

    def tearDown(self):
        self.service_patch.stop()
        self.auth_patch.stop()

    @staticmethod
    def _headers():
        return {"Authorization": "Bearer admin-token"}

    def test_bulk_action_deduplicates_and_sorts_delivery_ids(self):
        response = self.client.post(
            "/message-hub/deliveries/bulk-action",
            json={"action": "acknowledge", "delivery_ids": [12, "11", 12]},
            headers=self._headers(),
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual([([11, 12], "acknowledge")], self.service.bulk_updates)
        self.assertEqual("alice", self.service.bulk_audits[0]["actor_username"])
        self.assertEqual(3, self.service.bulk_audits[0]["actor_user_id"])
        self.assertEqual(2, response.get_json()["updated"])

    def test_bulk_action_rejects_unsupported_action(self):
        response = self.client.post(
            "/message-hub/deliveries/bulk-action",
            json={"action": "delete", "delivery_ids": [11]},
            headers=self._headers(),
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual([], self.service.bulk_updates)

    def test_bulk_action_rejects_more_than_500_unique_ids(self):
        response = self.client.post(
            "/message-hub/deliveries/bulk-action",
            json={"action": "cancel", "delivery_ids": list(range(1, 502))},
            headers=self._headers(),
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual([], self.service.bulk_updates)

    def test_delivery_search_parses_filters_and_pagination(self):
        response = self.client.get(
            "/message-hub/deliveries/search",
            query_string={
                "statuses": "held,dead",
                "gateway_key": "sms-main",
                "recipient": "+4712",
                "query": "hello",
                "created_after": "2026-09-01T00:00:00Z",
                "sort": "asc",
                "page": "2",
                "page_size": "50",
            },
            headers=self._headers(),
        )

        self.assertEqual(200, response.status_code)
        filters = self.service.delivery_searches[0]
        self.assertEqual(["held", "dead"], filters["statuses"])
        self.assertEqual("sms-main", filters["gateway_key"])
        self.assertEqual("+4712", filters["recipient"])
        self.assertEqual("hello", filters["query"])
        self.assertEqual("asc", filters["sort"])
        self.assertEqual(2, filters["page"])
        self.assertEqual(50, filters["page_size"])
        self.assertIsNotNone(filters["created_after"].tzinfo)

    def test_delivery_search_rejects_an_invalid_status(self):
        response = self.client.get(
            "/message-hub/deliveries/search?statuses=held,missing",
            headers=self._headers(),
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual([], self.service.delivery_searches)

    def test_group_search_uses_the_delivery_filters(self):
        response = self.client.get(
            "/message-hub/delivery-groups/search?statuses=held&source_type=telegram&source_label=Family",
            headers=self._headers(),
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("telegram", self.service.group_searches[0]["source_type"])
        self.assertEqual("Family", self.service.group_searches[0]["source_label"])

    def test_group_bulk_action_passes_an_exact_group_identity(self):
        response = self.client.post(
            "/message-hub/delivery-groups/bulk-action",
            json={
                "action": "acknowledge",
                "statuses": ["held"],
                "gateway_key": "sms-main",
                "recipient_key": "sms:+4712",
                "source_type": "telegram",
                "source_label": "Family",
                "conversation_key": "family-chat",
                "created_after": "2026-09-01T00:00:00Z",
            },
            headers=self._headers(),
        )

        self.assertEqual(200, response.status_code)
        group = self.service.group_updates[0]
        self.assertEqual("acknowledge", group["action"])
        self.assertEqual("family-chat", group["conversation_key"])
        self.assertIsNotNone(group["created_after"].tzinfo)

    def test_filtered_bulk_action_passes_the_filter_snapshot(self):
        response = self.client.post(
            "/message-hub/deliveries/bulk-filter-action",
            json={
                "action": "cancel",
                "filters": {
                    "statuses": ["held"],
                    "gateway_key": "sms-main",
                    "recipient": "+4712",
                    "query": "hello",
                    "source_type": "telegram",
                    "source_label": "Family",
                    "created_before": "2026-09-23T12:00:00Z",
                },
            },
            headers=self._headers(),
        )

        self.assertEqual(200, response.status_code)
        filters = self.service.filtered_updates[0]
        self.assertEqual("cancel", filters["action"])
        self.assertEqual(["held"], filters["statuses"])
        self.assertEqual("sms-main", filters["gateway_key"])
        self.assertEqual("Family", filters["source_label"])
        self.assertIsNotNone(filters["created_before"].tzinfo)

    def test_filtered_bulk_action_rejects_missing_statuses(self):
        response = self.client.post(
            "/message-hub/deliveries/bulk-filter-action",
            json={"action": "cancel", "filters": {}},
            headers=self._headers(),
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual([], self.service.filtered_updates)

    def test_bulk_operation_history_undo_and_resume(self):
        history = self.client.get(
            "/message-hub/bulk-operations?limit=5",
            headers=self._headers(),
        )
        undone = self.client.post(
            "/message-hub/bulk-operations/7/undo",
            headers=self._headers(),
        )
        resumed = self.client.post(
            "/message-hub/bulk-operations/7/resume",
            headers=self._headers(),
        )

        self.assertEqual(200, history.status_code)
        self.assertEqual(7, history.get_json()[0]["id"])
        self.assertEqual(2, undone.get_json()["restored"])
        self.assertEqual(1, resumed.get_json()["updated"])
        self.assertEqual([7], self.service.undo_calls)
        self.assertEqual([7], self.service.resume_calls)

    def test_delivery_details_returns_the_composed_record(self):
        response = self.client.get(
            "/message-hub/deliveries/10",
            headers=self._headers(),
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(10, response.get_json()["delivery"]["id"])

    def test_delivery_details_returns_not_found(self):
        response = self.client.get(
            "/message-hub/deliveries/404",
            headers=self._headers(),
        )

        self.assertEqual(404, response.status_code)

    def test_delivery_details_requires_an_administrator(self):
        with patch("src.auth.decode_token", return_value={"is_admin": False}):
            response = self.client.get(
                "/message-hub/deliveries/10",
                headers=self._headers(),
            )

        self.assertEqual(403, response.status_code)


if __name__ == "__main__":
    unittest.main()
