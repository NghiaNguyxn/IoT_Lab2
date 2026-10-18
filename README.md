# Bài Thực Hành Số 2: Thu Thập, Lưu Trữ Và Tiền Xử Lý Dữ Liệu IoT

* **Học phần:** IoT và Ứng dụng (INT14149)
* **Sinh viên thực hiện:** Nguyễn Trung Nghĩa
* **Thiết bị mô phỏng:** ESP32 DevKit V1 + Cảm biến nhiệt độ, độ ẩm (DHT22) + Cảm biến khoảng cách siêu âm (HC-SR04)

---

## 1. Giới thiệu chung

Dự án xây dựng một đường ống dữ liệu (Data Pipeline) IoT hoàn chỉnh từ tầng thiết bị cảm biến (Edge) đến cơ sở dữ liệu chuỗi thời gian (Time-Series Database) và ứng dụng giám sát trực quan:
1. **Thiết bị nhúng (ESP32 trên Wokwi):** Đọc nhiệt độ ($^\circ\text{C}$), độ ẩm ($\%$) từ cảm biến `DHT22` và khoảng cách ($\text{cm}$) từ cảm biến `HC-SR04`, đóng gói thành bản tin JSON và publish định kỳ mỗi $5.000\text{ ms}$ lên MQTT Broker.
2. **Dịch vụ thu thập (`collector.py`):** Subscribe topic MQTT từ `broker.hivemq.com`, kiểm tra tính hợp lệ của cấu trúc JSON, miền giá trị vật lý, khử trùng lặp theo `sequence` và ghi đồng bộ vào measurement `sensor_raw` trong **InfluxDB 2.x**.
3. **Tiền xử lý dữ liệu (`clean_data.py` & `save_clean.py`):** Truy vấn dữ liệu thô, phát hiện và loại bỏ điểm ngoại lai (Outlier) bằng phương pháp tứ phân vị $\text{IQR}$, gom mẫu (Resampling) theo cửa sổ $10\text{ giây}$, nội suy tuyến tính các khoảng trống ngắn (`limit = 2`), tạo đặc trưng trung bình trượt (`_rolling_mean`), độ biến thiên (`_delta`), chuẩn hóa Min–Max về đoạn $[0, 1]$ và ghi vào measurement `sensor_clean`.
4. **Ứng dụng giám sát (`dashboard.py`):** Giao diện Desktop (`Tkinter` + `Matplotlib`) trực quan hóa song song chuỗi dữ liệu thô (`sensor_raw`), dữ liệu đã làm sạch (`sensor_clean`) và đường trung bình trượt.

---

## 2. Sơ đồ kiến trúc hệ thống

```text
[ ESP32 trên Wokwi (DHT22 + HC-SR04) ]
       │ (Publish JSON mỗi 5s qua MQTT)
       ▼
[ MQTT Broker: broker.hivemq.com:1883 ]
       │ (Subscribe topic: ptit/Nghia_lab2/esp32_01/telemetry)
       ▼
[ Python Collector: collector.py ]
       │ (Kiểm tra JSON, miền giá trị & Ghi dữ liệu thô)
       ▼
[ InfluxDB 2.x Local: Org "iot_lab" / Bucket "iot_data" (sensor_raw) ]
       │ (Truy vấn dữ liệu thô / Tiền xử lý / Ghi dữ liệu sạch)
       ├──► [ Python Preprocessor: clean_data.py & save_clean.py ] ──► (sensor_clean)
       └──► [ Dashboard Real-time: dashboard.py (Tkinter + Matplotlib) ]
```

---

## 3. Cấu trúc thư mục dự án

```text
IoT_Bai2/
├── firmware/
│   ├── sketch.ino            # Mã nguồn nạp cho ESP32 trên Wokwi
│   ├── diagram.json          # Sơ đồ nối dây mạch mô phỏng Wokwi
│   └── libraries.txt         # Danh sách thư viện Arduino sử dụng trên Wokwi
├── collector.py              # Script nhận bản tin MQTT, kiểm tra hợp lệ và ghi vào sensor_raw
├── clean_data.py             # Script lọc IQR, Resample 10s, nội suy, tạo đặc trưng & chuẩn hóa
├── save_clean.py             # Script ghi dữ liệu sau xử lý từ sensor_clean.csv vào InfluxDB
├── dashboard.py              # Ứng dụng GUI Tkinter + Matplotlib hiển thị biểu đồ Raw vs Clean
├── sensor_raw.csv            # Tập dữ liệu thô xuất từ InfluxDB (38 bản ghi)
├── sensor_clean.csv          # Tập dữ liệu sau tiền xử lý (104 cửa sổ 10 giây)
├── scaling_params.json       # Tham số chuẩn hóa Min-Max của từng đại lượng đo
└── README.md                 # Tài liệu hướng dẫn cài đặt và vận hành hệ thống
```

---

## 4. Yêu cầu hệ thống & Cài đặt môi trường

### 4.1. Phần mềm cần thiết
* **Hệ điều hành:** Windows 10 / 11, macOS hoặc Linux.
* **Python:** Phiên bản `3.10+` (đã kiểm thử trên `Python 3.11.9`).
* **Cơ sở dữ liệu:** **InfluxDB 2.x** (`v2.10.0` chạy độc lập qua `influxd.exe` tại `http://localhost:8086`).

### 4.2. Cài đặt môi trường ảo và thư viện Python
Mở **PowerShell** tại thư mục gốc của dự án và chạy các lệnh sau:

```powershell
# 1. Tạo môi trường ảo .venv
python -m venv .venv

# 2. Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# 3. Cài đặt các thư viện cần thiết
pip install paho-mqtt influxdb-client pandas numpy scikit-learn matplotlib
```

---

## 5. Hướng dẫn khởi chạy hệ thống từng bước

### Bước 1: Khởi động InfluxDB 2.x và cấu hình Token
1. Mở một cửa sổ PowerShell riêng và khởi chạy máy chủ InfluxDB:
   ```powershell
   C:\Users\Admin\TH2\influxdb\influxd.exe
   ```
   *(Giữ cửa sổ này mở trong suốt quá trình thu thập và xử lý dữ liệu).*
2. Trên giao diện `http://localhost:8086`, đảm bảo đã khởi tạo:
   * **Organization:** `ptit_iot_lab`
   * **Bucket:** `iot_data` (Retention Policy: `7 ngày`)
3. Dán mã API Token (88 ký tự) vào tệp `influx_token.txt` đặt tại thư mục gốc của dự án.

### Bước 2: Chạy mô phỏng thiết bị nhúng trên Wokwi
1. Truy cập [Wokwi Simulator](https://wokwi.com/), tạo project ESP32 mới.
2. Copy nội dung `firmware/sketch.ino`, `firmware/diagram.json` và `firmware/libraries.txt` vào các tab tương ứng trên Wokwi.
3. Nhấn nút **Start the simulation (Play)**. Thiết bị sẽ kết nối vào WiFi `Wokwi-GUEST` và gửi gói tin JSON mỗi $5\text{ giây}$ lên topic `ptit/Nghia_lab2/esp32_01/telemetry` tại broker `broker.hivemq.com:1883`.

### Bước 3: Chạy dịch vụ thu thập dữ liệu (`collector.py`)
Trong cửa sổ PowerShell đã kích hoạt `.venv`, chạy lệnh:
```powershell
python collector.py
```
* Chương trình sẽ lắng nghe topic MQTT, kiểm tra tính hợp lệ của bản tin và in ra thông báo:
  ```text
  Da doc token tu tep, so ky tu: 88
  Da ket noi MQTT Broker! Dang lang nghe topic: ptit/Nghia_lab2/esp32_01/telemetry
  DA LUU | seq=1 | temp=29.58 | hum=67.19 | dist=106.56
  ```
* Sau khi thu thập đủ số lượng bản ghi cần thiết, nhấn `Ctrl + C` để dừng thu thập.

### Bước 4: Chạy tiền xử lý dữ liệu và lưu vào cơ sở dữ liệu
Chạy lần lượt 2 lệnh sau để làm sạch dữ liệu và lưu vào measurement `sensor_clean`:
```powershell
# 1. Truy vấn sensor_raw, lọc IQR, Resample 10s, nội suy, chuẩn hóa và xuất CSV
python clean_data.py

# 2. Ghi kết quả đã làm sạch vào measurement sensor_clean trong InfluxDB
python save_clean.py
```

### Bước 5: Mở ứng dụng Dashboard giám sát (`dashboard.py`)
Khởi chạy giao diện đồ họa để xem biểu đồ so sánh trực quan giữa dữ liệu gốc và dữ liệu đã qua tiền xử lý:
```powershell
python dashboard.py
```

---

## 6. Tóm tắt kết quả thực nghiệm

| Chỉ số thống kê | Nhiệt độ (`temperature`, $^\circ\text{C}$) | Độ ẩm (`humidity`, $\%$) | Khoảng cách (`distance_cm`, $\text{cm}$) |
| :--- | :---: | :---: | :---: |
| **Số bản ghi gốc (`sensor_raw`)** | $38$ | $38$ | $38$ |
| **Ngưỡng lọc IQR $[Q_1 - 1,5\text{IQR};\ Q_3 + 1,5\text{IQR}]$** | $[25,624;\ 32,494]$ | $[58,056;\ 72,306]$ | $[95,059;\ 116,029]$ |
| **Số điểm bất thường bị loại bỏ (Outliers)** | $1$ ($38,50^\circ\text{C}$) | $1$ ($85,00\%$) | $1$ ($145,00\text{ cm}$) |
| **Số ô thiếu sau khi gom cửa sổ $10\text{s}$** | $70$ | $70$ | $70$ |
| **Số ô còn thiếu sau nội suy (`limit = 2`)** | $62$ *(nội suy 8 ô)* | $62$ *(nội suy 8 ô)* | $63$ *(nội suy 7 ô)* |
| **Tổng số cửa sổ $10\text{s}$ ghi vào `sensor_clean`** | $104$ | $104$ | $104$ |