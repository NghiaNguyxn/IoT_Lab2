import tkinter as tk
from tkinter import ttk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class IoTDashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IoT Real-time Dashboard - Nguyễn Trung Nghĩa")
        self.root.geometry("1050x760")

        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X)

        self.btn_reload = ttk.Button(top_frame, text="🔄 Tải lại dữ liệu (Raw vs Clean)", command=self.update_charts)
        self.btn_reload.pack(side=tk.LEFT, padx=10)

        self.lbl_status = ttk.Label(top_frame, text="Trạng thái: Sẵn sàng", font=("Segoe UI", 10, "bold"))
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        self.fig, self.axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.update_charts()

    def update_charts(self):
        try:
            raw_df = pd.read_csv("sensor_raw.csv")
            clean_df = pd.read_csv("sensor_clean.csv")
            raw_df["_time"] = pd.to_datetime(raw_df["_time"])
            clean_df["_time"] = pd.to_datetime(clean_df["_time"])

            for ax in self.axes:
                ax.clear()

            configs = [
                ("temperature", "Nhiệt độ (°C)", "tab:red"),
                ("humidity", "Độ ẩm (%)", "tab:blue"),
                ("distance_cm", "Khoảng cách (cm)", "tab:green"),
            ]

            for ax, (col, label, color) in zip(self.axes, configs):
                ax.plot(raw_df["_time"], raw_df[col], "o--", alpha=0.55, color=color, label=f"Raw ({col})")
                ax.plot(clean_df["_time"], clean_df[col], "s-", linewidth=1.6, color="black", label=f"Clean 10s ({col})")
                ax.plot(clean_df["_time"], clean_df[f"{col}_rolling_mean"], "-", linewidth=2.0, color="orange", label="Rolling Mean (3 cửa sổ)")
                ax.set_ylabel(label)
                ax.legend(loc="upper right", fontsize=8)
                ax.grid(True, linestyle=":", alpha=0.6)

            self.axes[0].set_title("So sánh dữ liệu thô (sensor_raw) và dữ liệu sau tiền xử lý (sensor_clean)")
            self.axes[-1].set_xlabel("Thời gian (UTC)")
            self.fig.tight_layout()
            self.canvas.draw()
            self.lbl_status.config(text=f"Đã tải: {len(raw_df)} bản ghi Raw | {len(clean_df)} cửa sổ Clean (10s)")
        except Exception as e:
            self.lbl_status.config(text=f"Lỗi đọc dữ liệu: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = IoTDashboardApp(root)
    root.mainloop()