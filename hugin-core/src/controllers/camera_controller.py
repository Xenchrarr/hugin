from flask import Blueprint, Response

from src.clients.unifi import UnifiClient

camera_blueprint = Blueprint("camera", __name__)

unifi_client = UnifiClient()


@camera_blueprint.route('/snapshot')
def snapshot():
    image = unifi_client.download_image()
    if image is None:
        return {"error": "Could not fetch camera snapshot"}, 502
    return Response(image, mimetype="image/jpeg")
