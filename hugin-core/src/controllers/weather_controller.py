from flask import Blueprint, Response

from src.clients.yr import YrClient

weather_blueprint = Blueprint("weather", __name__)

yr_client = YrClient()


@weather_blueprint.route("/<location_id>")
def weather_image(location_id: str):
    image = yr_client.get_weather_image(yr_id=location_id)
    if image is None:
        return {"error": "Could not fetch weather image"}, 502
    return Response(image, mimetype="image/png")
