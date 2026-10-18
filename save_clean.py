from pathlib import Path
import pandas as pd
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = Path("influx_token.txt").read_text(encoding="utf-8").strip()
INFLUX_ORG = "ptit_iot_lab"
INFLUX_BUCKET = "iot_data"
DEVICE_ID = "esp32_01"

SENSOR_COLS = ["temperature", "humidity", "distance_cm"]
INT_COLS = ["sample_count", "outlier_count", "interpolated_count"]

def main():
    print(f"Da doc token tu tep, so ky tu: {len(INFLUX_TOKEN)}\n")
    clean_df = pd.read_csv("sensor_clean.csv", index_col=0, parse_dates=True)

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    points = []
    windows_with_data = 0

    for ts, row in clean_df.iterrows():
        p = Point("sensor_clean").tag("device_id", DEVICE_ID)
        if any(pd.notna(row[c]) for c in SENSOR_COLS):
            windows_with_data += 1

        for col in clean_df.columns:
            val = row[col]
            if pd.notna(val):
                if col in INT_COLS:
                    p = p.field(col, int(val))
                else:
                    p = p.field(col, float(val))
        p = p.time(ts.to_pydatetime(), WritePrecision.MS)
        points.append(p)

    if points:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
    client.close()

    print("LUU THANH CONG")
    print("Measurement: sensor_clean")
    print(f"Tong so cua so da ghi: {len(points)}")
    print(f"So cua so co it nhat mot so do: {windows_with_data}")
    print("Cua so thieu van duoc luu cac cot dem.")

if __name__ == "__main__":
    main()