from __future__ import annotations

from datetime import datetime

from flask import Blueprint, request

from src.models.orchestrator.Reminder import Reminder, NotificationSetting
from src.persistence.ReminderStorage import ReminderStorage
from src.services.core.reminder_scheduler_service import ReminderSchedulerService

reminder_blueprint = Blueprint('reminders', __name__)

_storage = ReminderStorage()


@reminder_blueprint.route('/list', methods=['GET'])
def list_reminders():
    try:
        status = request.args.get('status')
        user_id_param = request.args.get('user_id')
        user_id = int(user_id_param) if user_id_param else None
        reminders = _storage.get_reminders(status_filter=status, user_id=user_id)
        return [r.to_dict() for r in reminders]
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/<int:reminder_id>', methods=['GET'])
def get_reminder(reminder_id: int):
    try:
        reminder = _storage.get_reminder(reminder_id)
        if reminder is None:
            return {'message': 'Reminder not found', 'status': 404}, 404
        return reminder.to_dict()
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/', methods=['POST'])
def create_reminder():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing or invalid JSON body', 'status': 400}, 400

        if not data.get('title'):
            return {'message': 'Missing required field: title', 'status': 400}, 400
        if not data.get('due_at'):
            return {'message': 'Missing required field: due_at', 'status': 400}, 400

        # Parse due_at string to datetime
        due_at = data.get('due_at')
        if isinstance(due_at, str):
            due_at = datetime.fromisoformat(due_at)
        data['due_at'] = due_at

        reminder = Reminder.from_dict(data)
        reminder.status = 'active'

        created = _storage.create_reminder(reminder)

        # Schedule it
        scheduler = ReminderSchedulerService.instance()
        job_id = scheduler.schedule_reminder(created)
        created.scheduler_job_id = job_id
        _storage.update_reminder(created)

        _storage.add_reminder_history(created.id, 'created', detail=f"via {created.created_by}")

        return created.to_dict(), 201

    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/<int:reminder_id>', methods=['PUT'])
def update_reminder(reminder_id: int):
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing or invalid JSON body', 'status': 400}, 400

        existing = _storage.get_reminder(reminder_id)
        if existing is None:
            return {'message': 'Reminder not found', 'status': 404}, 404

        due_at = data.get('due_at', existing.due_at)
        if isinstance(due_at, str):
            due_at = datetime.fromisoformat(due_at)

        existing.title = data.get('title', existing.title)
        existing.message = data.get('message', existing.message)
        existing.due_at = due_at
        existing.recurrence = data.get('recurrence', existing.recurrence)
        existing.recipient_ids = data.get('recipient_ids', existing.recipient_ids)
        if 'user_id' in data:
            existing.user_id = data['user_id']

        updated = _storage.update_reminder(existing)

        # Reschedule
        scheduler = ReminderSchedulerService.instance()
        job_id = scheduler.reschedule_reminder(updated)
        updated.scheduler_job_id = job_id
        _storage.update_reminder(updated)

        return updated.to_dict()

    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/<int:reminder_id>', methods=['DELETE'])
def delete_reminder(reminder_id: int):
    try:
        existing = _storage.get_reminder(reminder_id)
        if existing is None:
            return {'message': 'Reminder not found', 'status': 404}, 404

        scheduler = ReminderSchedulerService.instance()
        scheduler.unschedule_reminder(existing)

        _storage.delete_reminder(reminder_id)
        return {'message': 'Reminder deleted', 'status': 200}

    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/<int:reminder_id>/snooze', methods=['POST'])
def snooze_reminder(reminder_id: int):
    try:
        data = request.get_json(silent=True) or {}
        duration = data.get('duration', '10m')

        minutes = _parse_duration(duration)
        scheduler = ReminderSchedulerService.instance()
        updated = scheduler.snooze_reminder(reminder_id, minutes)

        return updated.to_dict()

    except ValueError as e:
        return {'message': str(e), 'status': 400, 'error': str(e)}, 400
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/<int:reminder_id>/dismiss', methods=['POST'])
def dismiss_reminder(reminder_id: int):
    try:
        scheduler = ReminderSchedulerService.instance()
        updated = scheduler.dismiss_reminder(reminder_id)

        return updated.to_dict()

    except ValueError as e:
        return {'message': str(e), 'status': 400, 'error': str(e)}, 400
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/<int:reminder_id>/history', methods=['GET'])
def get_reminder_history(reminder_id: int):
    try:
        history = _storage.get_reminder_history(reminder_id)
        return [h.to_dict() for h in history]
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/notification-settings', methods=['GET'])
def get_notification_settings():
    try:
        settings = _storage.get_notification_settings()
        return [s.to_dict() for s in settings]
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/notification-settings', methods=['POST', 'PUT'])
def update_notification_settings():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing or invalid JSON body', 'status': 400}, 400

        # Accept a single setting or a list
        settings_list = data if isinstance(data, list) else [data]

        results = []
        for item in settings_list:
            setting = NotificationSetting.from_dict(item)
            saved = _storage.upsert_notification_setting(setting)
            results.append(saved.to_dict())

        return results

    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@reminder_blueprint.route('/notification-settings/<int:setting_id>', methods=['DELETE'])
def delete_notification_setting(setting_id: int):
    try:
        deleted = _storage.delete_notification_setting(setting_id)
        if not deleted:
            return {'message': 'Not found', 'status': 404}, 404
        return {'message': 'Deleted', 'id': setting_id}
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


def _parse_duration(duration: str) -> int:
    """Parse duration string like '10m', '1h', '30' into minutes."""
    duration = duration.strip().lower()
    if duration.endswith('m'):
        return int(duration[:-1])
    elif duration.endswith('h'):
        return int(duration[:-1]) * 60
    elif duration.endswith('d'):
        return int(duration[:-1]) * 1440
    else:
        return int(duration)
