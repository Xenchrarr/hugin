from flask import Blueprint, Response, jsonify, request

from src.clients.yr import YrClient

weather_blueprint = Blueprint("weather", __name__)

yr_client = YrClient()


@weather_blueprint.route("/<location_id>")
def weather_image(location_id: str):
    dark_mode = request.args.get("dark", "true").lower() != "false"
    image = yr_client.get_weather_image(yr_id=location_id, dark_mode=dark_mode)
    if image is None:
        return {"error": "Could not fetch weather image"}, 502
    return Response(image, mimetype="image/png")


@weather_blueprint.route("/<location_id>/summary")
def weather_summary(location_id: str):
    summary = yr_client.get_weather_summary(yr_id=location_id)
    if summary is None:
        return {"error": "Could not fetch weather summary"}, 502
    return jsonify(summary)
