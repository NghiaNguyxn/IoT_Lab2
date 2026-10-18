import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from influxdb_client import InfluxDBClient

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = Path("influx_token.txt").read_text(encoding="utf-8").strip()
INFLUX_ORG = "ptit_iot_lab"
INFLUX_BUCKET = "iot_data"
DEVICE_ID = "esp32_01"

SENSOR_COLS = ["temperature", "humidity", "distance_cm"]

def main():
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()

    # Truy vấn dữ liệu vừa thu trong 30 phút gần nhất
    flux_query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -30m)
      |> filter(fn: (r) => r["_measurement"] == "sensor_raw")
      |> filter(fn: (r) => r["device_id"] == "{DEVICE_ID}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
    '''
    df_raw = query_api.query_data_frame(flux_query)
    client.close()

    if isinstance(df_raw, list):
        df_raw = pd.concat(df_raw, ignore_index=True)

    if df_raw.empty:
        print("Khong tim thay du lieu trong sensor_raw!")
        return

    df_raw["_time"] = pd.to_datetime(df_raw["_time"], utc=True)
    df_raw = df_raw.set_index("_time").sort_index()
    df_raw.to_csv("sensor_raw.csv")
    print(f"SO BAN GHI GOC: {len(df_raw)}\n")

    df = df_raw[SENSOR_COLS].apply(pd.to_numeric, errors="coerce").copy()

    # 1. Phát hiện bất thường bằng IQR
    print("PHAT HIEN BAT THUONG BANG IQR:")
    outlier_flags = pd.DataFrame(False, index=df.index, columns=SENSOR_COLS)
    for col in SENSOR_COLS:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        if iqr > 1e-6:
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            mask = (df[col] < lower) | (df[col] > upper)
            outlier_flags[col] = mask
            count = int(mask.sum())
            df.loc[mask, col] = np.nan
            print(f"{col}: nguong [{lower:.3f}, {upper:.3f}], so diem bat thuong = {count}")
        else:
            print(f"{col} : IQR gan 0, khong tu dong loai")

    # 2. Gom cửa sổ 10 giây (Resampling)
    resampled = df.resample("10s").mean()
    sample_counts = df_raw["temperature"].resample("10s").count()
    outlier_counts = outlier_flags.any(axis=1).astype(int).resample("10s").sum()

    print("\nSO O THIEU SAU KHI GOM CUA SO:")
    for col in SENSOR_COLS:
        print(f"{col:15s} {int(resampled[col].isna().sum())}")

    # 3. Nội suy theo thời gian tối đa 2 cửa sổ liên tiếp
    before_na = resampled[SENSOR_COLS].isna()
    clean_df = resampled.interpolate(method="time", limit=2)
    after_na = clean_df[SENSOR_COLS].isna()

    print("\nSO O CON THIEU SAU NOI SUY:")
    for col in SENSOR_COLS:
        print(f"{col:15s} {int(clean_df[col].isna().sum())}")

    clean_df["sample_count"] = sample_counts
    clean_df["outlier_count"] = outlier_counts
    clean_df["interpolated_count"] = (before_na & ~after_na).any(axis=1).astype(int)

    # 4. Tạo đặc trưng Rolling Mean (3 cửa sổ) và Delta
    for col in SENSOR_COLS:
        clean_df[f"{col}_rolling_mean"] = clean_df[col].rolling(window=3, min_periods=1).mean()
        clean_df[f"{col}_delta"] = clean_df[col].diff()

    # 5. Chuẩn hóa Min-Max
    scaler = MinMaxScaler()
    scaling_params = {}
    for col in SENSOR_COLS:
        valid = clean_df[col].notna()
        if valid.sum() > 0:
            if clean_df.loc[valid, col].nunique() > 1:
                clean_df.loc[valid, f"{col}_norm"] = scaler.fit_transform(clean_df.loc[valid, [col]]).flatten()
                scaling_params[col] = {"min": float(scaler.data_min_[0]), "max": float(scaler.data_max_[0])}
            else:
                clean_df.loc[valid, f"{col}_norm"] = 0.0
                val = float(clean_df.loc[valid, col].iloc[0])
                scaling_params[col] = {"min": val, "max": val}

    clean_df.to_csv("sensor_clean.csv")
    with open("scaling_params.json", "w", encoding="utf-8") as f:
        json.dump(scaling_params, f, indent=2)

if __name__ == "__main__":
    main()