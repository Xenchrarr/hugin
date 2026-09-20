import logging
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

from src.config.logging import setup_logging
from src.sms_handler import SMSHandler
from src.command_processor import CommandProcessor
from src.api.sms_api import start_api_server
from src.models.command_response import CommandResponse
from src.mms.decoder import MmsNotification

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PendingResponse:
    phone: str
    text: str
    idempotency_key: str
    source_type: str
    source_label: str
    acknowledge_delivery_ids: list[int] = field(default_factory=list)
    modem_message_index: str | None = None
    image_bytes: bytes | None = None
    image_mime: str = "image/jpeg"


def _queue_response(
    processor: CommandProcessor,
    pending: PendingResponse,
) -> bool:
    if pending.image_bytes is not None:
        queued = processor.queue_mms_response(
            pending.phone,
            pending.text,
            pending.image_bytes,
            pending.image_mime,
            pending.idempotency_key,
            source_type=pending.source_type,
            source_label=pending.source_label,
            acknowledge_delivery_ids=pending.acknowledge_delivery_ids,
        )
    elif not pending.text or pending.text.startswith("OK"):
        return True
    else:
        queued = processor.queue_sms_response(
            pending.phone,
            pending.text,
            pending.idempotency_key,
            source_type=pending.source_type,
            source_label=pending.source_label,
            acknowledge_delivery_ids=pending.acknowledge_delivery_ids,
        )
    if not queued:
        logger.error(
            "Could not queue %s response %s",
            pending.source_type,
            pending.idempotency_key,
        )
    return queued


def _submit_pending_response(
    processor: CommandProcessor,
    sms: SMSHandler,
    pending: PendingResponse,
) -> bool:
    if not _queue_response(processor, pending):
        return False
    if pending.modem_message_index is not None:
        return sms.delete_message(pending.modem_message_index)
    return True


def main():
    setup_logging()

    sms = SMSHandler()
    processor = CommandProcessor()
    pending_responses: dict[str, PendingResponse] = {}

    # Start the outbound SMS REST API in a background thread
    start_api_server(sms)

    try:
        while True:
            for key, pending in list(pending_responses.items()):
                if _submit_pending_response(processor, sms, pending):
                    pending_responses.pop(key, None)

            for caller in sms.poll_incoming_calls():
                response = processor.process_missed_call(caller)
                if isinstance(response, CommandResponse):
                    key = f"missed-call:{caller}:{int(time.time() // 60)}"
                    pending = PendingResponse(
                        phone=caller,
                        text=response.text,
                        idempotency_key=key,
                        source_type="missed-call",
                        source_label="Missed call command",
                        acknowledge_delivery_ids=response.ack_hub_delivery_ids,
                        image_bytes=response.image_bytes,
                        image_mime=response.image_mime,
                    )
                    if not _submit_pending_response(processor, sms, pending):
                        pending_responses[key] = pending
                elif response:
                    key = f"missed-call:{caller}:{int(time.time() // 60)}"
                    pending = PendingResponse(
                        phone=caller,
                        text=response,
                        idempotency_key=key,
                        source_type="missed-call",
                        source_label="Missed call command",
                    )
                    if not _submit_pending_response(processor, sms, pending):
                        pending_responses[key] = pending

            messages = sms.read_messages()
            for msg in messages:
                if isinstance(msg, MmsNotification):
                    response_key = f"mms-command:{msg.transaction_id}"
                    if response_key in pending_responses:
                        continue
                    logger.info(
                        "Received MMS notification from %s (transaction %s)",
                        msg.sender,
                        msg.transaction_id,
                    )
                    retrieved = sms.retrieve_mms(msg)
                    if retrieved is None:
                        # Keep the notification in modem storage so a temporary
                        # carrier or Telegram failure can be retried.
                        continue
                    result = processor.process_media(
                        caption=retrieved.caption,
                        sender=msg.sender,
                        image_bytes=retrieved.image_bytes,
                        image_mime=retrieved.image_mime,
                    )
                    if not result.handled:
                        continue
                    pending = PendingResponse(
                        phone=msg.sender,
                        text=result.response,
                        idempotency_key=response_key,
                        source_type="mms-command",
                        source_label="MMS command",
                        modem_message_index=msg.index,
                    )
                    if not _submit_pending_response(processor, sms, pending):
                        pending_responses[response_key] = pending
                    continue

                logger.info("Received SMS from %s: %s", msg.sender, msg.text)

                response_key = f"sms-command:{msg.sender}:{msg.date}:{msg.index}"
                if response_key in pending_responses:
                    continue
                response = processor.process(msg.text, sender=msg.sender)
                if isinstance(response, CommandResponse):
                    pending = PendingResponse(
                        phone=msg.sender,
                        text=response.text,
                        idempotency_key=response_key,
                        source_type="sms-command",
                        source_label="SMS command",
                        acknowledge_delivery_ids=response.ack_hub_delivery_ids,
                        modem_message_index=msg.index,
                        image_bytes=response.image_bytes,
                        image_mime=response.image_mime,
                    )
                    if not _submit_pending_response(processor, sms, pending):
                        pending_responses[response_key] = pending
                else:
                    pending = PendingResponse(
                        phone=msg.sender,
                        text=response,
                        idempotency_key=response_key,
                        source_type="sms-command",
                        source_label="SMS command",
                        modem_message_index=msg.index,
                    )
                    if not _submit_pending_response(processor, sms, pending):
                        pending_responses[response_key] = pending

            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Exiting gracefully.")
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
    finally:
        sms.close()


if __name__ == "__main__":
    main()
