import json
import os
import ssl
import sys

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from ecoflow_client import EcoflowClient

load_dotenv()

client = EcoflowClient(
    access_key=os.environ["ECOFLOW_ACCESS_KEY"],
    secret_key=os.environ["ECOFLOW_SECRET_KEY"],
    base_url=os.environ.get("ECOFLOW_BASE_URL", "https://api-e.ecoflow.com"),
)

# Get device SN
devices = client.get_device_list().json()
device_sn = devices["data"][0]["sn"]
print(f"Device: {devices['data'][0]['deviceName']} ({device_sn}), online: {devices['data'][0]['online']}")

# Get MQTT credentials
cert = client.get_mqtt_certification().json()["data"]
print(f"MQTT broker: {cert['protocol']}://{cert['url']}:{cert['port']}")
print(f"Account: {cert['certificateAccount']}")

# Topics
topic_quota = f"/open/{cert['certificateAccount']}/{device_sn}/quota"
topic_status = f"/open/{cert['certificateAccount']}/{device_sn}/status"


def on_connect(mqttc, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"Connected to MQTT broker")
        mqttc.subscribe(topic_quota)
        mqttc.subscribe(topic_status)
        print(f"Subscribed to:\n  {topic_quota}\n  {topic_status}")
        print("Waiting for messages...\n")
    else:
        print(f"Connection failed with code {rc}")
        sys.exit(1)


def on_message(mqttc, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"[{topic}] Non-JSON: {msg.payload.decode()}")
        return

    if topic == topic_status:
        status = payload.get("params", {}).get("status", "?")
        print(f"[STATUS] Device {'ONLINE' if status == 1 else 'OFFLINE'}")
        return

    # Quota heartbeat — STREAM Microinverter fields (values already in W)
    params = payload.get("param", payload.get("params", payload))

    pv1 = params.get("powGetPv", None)
    pv2 = params.get("powGetPv2", None)
    grid_power = params.get("gridConnectionPower", None)
    grid_status = params.get("gridConnectionSta", None)

    if pv1 is not None or pv2 is not None or grid_power is not None:
        parts = []
        if pv1 is not None:
            parts.append(f"PV1: {pv1:.1f}W")
        if pv2 is not None:
            parts.append(f"PV2: {pv2:.1f}W")
        if grid_power is not None:
            parts.append(f"Grid: {grid_power:.1f}W")
        if grid_status is not None:
            parts.append(f"Status: {grid_status}")
        print(f"[QUOTA] {' | '.join(parts)}")
    else:
        # Other incremental updates — print raw
        print(f"[QUOTA] {json.dumps(params)}")


def on_disconnect(mqttc, userdata, rc, properties=None):
    print(f"Disconnected (rc={rc})")


mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.username_pw_set(cert["certificateAccount"], cert["certificatePassword"])
mqttc.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)

mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.on_disconnect = on_disconnect

print("Connecting...")
mqttc.connect(cert["url"], int(cert["port"]))

try:
    mqttc.loop_forever()
except KeyboardInterrupt:
    print("\nDisconnecting...")
    mqttc.disconnect()
