from flask import Blueprint, jsonify, request

from src.clients.google_calendar import GoogleCalendarClient

calendar_blueprint = Blueprint("calendar", __name__)

_client = GoogleCalendarClient()


@calendar_blueprint.route("/agenda")
def get_agenda():
    try:
        days = int(request.args.get("days", 7))
        days = max(1, min(days, 31))
    except (ValueError, TypeError):
        days = 7

    events = _client.get_events(days=days)
    return jsonify({"events": events})
