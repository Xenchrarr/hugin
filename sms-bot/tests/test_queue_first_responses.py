import unittest
import base64

import main as sms_main
from src.api.orchestrator import OrchestratorClient


class _Processor:
    def __init__(self, queued=True):
        self.queued = queued
        self.calls = []

    def queue_sms_response(self, phone, message, idempotency_key, **values):
        self.calls.append(("sms", phone, message, idempotency_key, values))
        return self.queued

    def queue_mms_response(
        self, phone, message, image_bytes, image_mime, idempotency_key, **values
    ):
        self.calls.append((
            "mms", phone, message, idempotency_key,
            {**values, "image_bytes": image_bytes, "image_mime": image_mime},
        ))
        return self.queued


class _Sms:
    def __init__(self, deleted=True):
        self.deleted = deleted
        self.delete_calls = []

    def delete_message(self, index):
        self.delete_calls.append(index)
        return self.deleted


class QueueFirstResponseTests(unittest.TestCase):
    def test_orchestrator_client_queues_replay_delivery_with_ack_links(self):
        client = OrchestratorClient("http://orchestrator:6000")
        captured = {}

        def fake_post(path, json=None):
            captured["path"] = path
            captured["body"] = json
            return {"message_id": 7, "deliveries": [{"id": 8, "status": "pending"}]}

        client._post = fake_post
        result = client.queue_sms_response(
            "+4712345678",
            "Waiting messages",
            "sms-command:key",
            acknowledge_delivery_ids=[41, 42],
        )

        self.assertEqual(7, result["message_id"])
        self.assertEqual("/api/message-hub/messages", captured["path"])
        body = captured["body"]
        self.assertEqual("sms-main", body["source_gateway_key"])
        self.assertEqual(15 * 60, body["ttl_seconds"])
        self.assertEqual("replay", body["deliveries"][0]["recovery_policy"])
        self.assertEqual(
            [41, 42], body["deliveries"][0]["acknowledge_delivery_ids"]
        )

    def test_orchestrator_client_queues_mms_attachment(self):
        client = OrchestratorClient("http://orchestrator:6000")
        captured = {}

        def fake_post(path, json=None):
            captured["path"] = path
            captured["body"] = json
            return {"message_id": 9, "deliveries": [{"id": 10}]}

        client._post = fake_post
        result = client.queue_mms_response(
            "+4712345678",
            "Weather forecast",
            b"png-data",
            "image/png",
            "sms-command:image",
        )

        self.assertEqual(9, result["message_id"])
        self.assertEqual("mms", captured["body"]["kind"])
        attachment = captured["body"]["attachments"][0]
        self.assertEqual("image/png", attachment["content_type"])
        self.assertEqual(
            b"png-data", base64.b64decode(attachment["data_base64"])
        )

    def test_pending_response_deletes_modem_message_only_after_queue_acceptance(self):
        pending = sms_main.PendingResponse(
            phone="+4712345678",
            text="hello",
            idempotency_key="sms-command:key",
            source_type="sms-command",
            source_label="SMS command",
            modem_message_index="4",
        )
        processor = _Processor(queued=False)
        sms = _Sms()

        self.assertFalse(sms_main._submit_pending_response(processor, sms, pending))
        self.assertEqual([], sms.delete_calls)

        processor.queued = True
        self.assertTrue(sms_main._submit_pending_response(processor, sms, pending))
        self.assertEqual(["4"], sms.delete_calls)
        self.assertEqual(
            ["sms-command:key", "sms-command:key"],
            [call[3] for call in processor.calls],
        )

    def test_suppressed_ok_response_is_not_enqueued_but_is_deleted(self):
        pending = sms_main.PendingResponse(
            phone="+4712345678",
            text="OK sent",
            idempotency_key="sms-command:key",
            source_type="sms-command",
            source_label="SMS command",
            modem_message_index="5",
        )
        processor = _Processor()
        sms = _Sms()

        self.assertTrue(sms_main._submit_pending_response(processor, sms, pending))
        self.assertEqual([], processor.calls)
        self.assertEqual(["5"], sms.delete_calls)

    def test_acknowledgement_ids_are_forwarded_to_the_queue(self):
        pending = sms_main.PendingResponse(
            phone="+4712345678",
            text="held messages",
            idempotency_key="sms-command:inbox",
            source_type="sms-command",
            source_label="SMS command",
            acknowledge_delivery_ids=[11, 12],
        )
        processor = _Processor()

        self.assertTrue(sms_main._submit_pending_response(processor, _Sms(), pending))
        self.assertEqual(
            [11, 12], processor.calls[0][4]["acknowledge_delivery_ids"]
        )

    def test_image_response_is_queued_as_mms_before_modem_message_is_deleted(self):
        pending = sms_main.PendingResponse(
            phone="+4712345678",
            text="Weather forecast",
            idempotency_key="sms-command:image",
            source_type="sms-command",
            source_label="SMS command",
            modem_message_index="9",
            image_bytes=b"png-data",
            image_mime="image/png",
        )
        processor = _Processor()
        sms = _Sms()

        self.assertTrue(sms_main._submit_pending_response(processor, sms, pending))

        self.assertEqual("mms", processor.calls[0][0])
        self.assertEqual(b"png-data", processor.calls[0][4]["image_bytes"])
        self.assertEqual("image/png", processor.calls[0][4]["image_mime"])
        self.assertEqual(["9"], sms.delete_calls)


if __name__ == "__main__":
    unittest.main()
