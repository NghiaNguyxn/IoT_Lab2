import json
import math
from datetime import datetime, timezone
from pathlib import Path
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Cấu hình MQTT khớp với code Wokwi vừa chạy
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "ptit/Nghia_lab2/esp32_01/telemetry"
DEVICE_ID = "esp32_01"

# Cấu hình InfluxDB đọc từ file influx_token.txt
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = Path("influx_token.txt").read_text(encoding="utf-8").strip()
INFLUX_ORG = "ptit_iot_lab"
INFLUX_BUCKET = "iot_data"

print(f"Da doc token tu tep, so ky tu: {len(INFLUX_TOKEN)}")

client_db = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client_db.write_api(write_options=SYNCHRONOUS)

last_sequence = None

def validate_payload(data: dict) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "JSON khong phai la mot doi tuong"

    required = ["temperature", "humidity", "distance_cm", "rssi", "sequence", "uptime_s"]
    for field in required:
        if field not in data:
            return False, f"Thieu truong bat buoc: {field}"

    # Kiểm tra sequence, uptime_s và rssi phải là số nguyên
    for int_field in ["sequence", "uptime_s", "rssi"]:
        if isinstance(data[int_field], bool) or not isinstance(data[int_field], int):
            return False, f"{int_field} phai la so nguyen"

    try:
        temp = float(data["temperature"])
        hum = float(data["humidity"])
        dist = float(data["distance_cm"])
        seq = int(data["sequence"])
        uptime = int(data["uptime_s"])
    except (ValueError, TypeError):
        return False, "Sai kieu du lieu"

    if not (math.isfinite(temp) and math.isfinite(hum) and math.isfinite(dist)):
        return False, "So do khong huu han"
    if not (0.0 <= hum <= 100.0):
        return False, "Do am ngoai khoang 0-100%"
    if dist < 0.0 or seq < 0 or uptime < 0:
        return False, "Khoang cach, sequence hoac uptime am"

    return True, "OK"

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Da ket noi MQTT Broker! Dang lang nghe topic: {MQTT_TOPIC}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global last_sequence
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception:
        print("BO QUA: Ban tin khong phai JSON hop le")
        return

    valid, reason = validate_payload(payload)
    if not valid:
        print(f"BO QUA ({reason}): {payload}")
        return

    seq = int(payload["sequence"])
    if last_sequence is not None and seq == last_sequence:
        print(f"BO QUA: Ban tin trung sequence={seq}")
        return
    last_sequence = seq

    point = (
        Point("sensor_raw")
        .tag("device_id", DEVICE_ID)
        .field("temperature", float(payload["temperature"]))
        .field("humidity", float(payload["humidity"]))
        .field("distance_cm", float(payload["distance_cm"]))
        .field("rssi", int(payload["rssi"]))
        .field("sequence", seq)
        .field("uptime_s", int(payload["uptime_s"]))
        .time(datetime.now(timezone.utc), WritePrecision.MS)
    )

    try:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        print(
            f"DA LUU | seq={seq} | temp={payload['temperature']} | "
            f"hum={payload['humidity']} | dist={payload['distance_cm']}"
        )
    except Exception as e:
        print(f"LOI GHI DB: {e}")

if __name__ == "__main__":
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    try:
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print("\nDa dung collector.py")