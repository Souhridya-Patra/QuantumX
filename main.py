import sys
import csv
from datetime import datetime
import serial
import numpy as np
from collections import deque
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QFrame,
    QGroupBox,
    QDoubleSpinBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
import pyqtgraph as pg

# SERIAL PORT (CHANGE IF NEEDED)
SERIAL_PORT = 'COM15'
BAUD_RATE = 9600

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.2)
except Exception:
    ser = None

class Dashboard(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Interferometer Pro Analyzer")
        self.setGeometry(80, 80, 1280, 760)

        pg.setConfigOptions(antialias=True)

        self.setStyleSheet(
            """
            QWidget {
                background-color: #f4f6f8;
                color: #111827;
                font-size: 13px;
            }
            QLabel#kpiValue {
                font-size: 22px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#kpiTitle {
                color: #475569;
                font-size: 12px;
            }
            QFrame#card {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QPushButton {
                padding: 8px 14px;
                border-radius: 8px;
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
            QLabel#alertOk {
                color: #166534;
                font-weight: 700;
            }
            QLabel#alertWarn {
                color: #b45309;
                font-weight: 700;
            }
            QLabel#alertBad {
                color: #b91c1c;
                font-weight: 700;
            }
            """
        )

        self.layout = QVBoxLayout()
        self.layout.setSpacing(12)

        # Buttons
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.save_btn = QPushButton("Save CSV")
        self.export_btn = QPushButton("Export Report")
        self.auto_calibrate_btn = QPushButton("Auto Calibrate")

        self.status_label = QLabel("Status: Disconnected" if ser is None else f"Status: Connected ({SERIAL_PORT})")

        controls = QHBoxLayout()
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.save_btn)
        controls.addWidget(self.export_btn)
        controls.addWidget(self.auto_calibrate_btn)
        controls.addWidget(self.status_label)
        controls.addStretch()
        self.layout.addLayout(controls)

        # Calibration and alerting controls
        calibrate_box = QGroupBox("Calibration and Thresholds")
        calibrate_layout = QGridLayout()

        self.min_input = QDoubleSpinBox()
        self.min_input.setRange(-1_000_000, 1_000_000)
        self.min_input.setValue(0.0)
        self.min_input.setDecimals(2)

        self.max_input = QDoubleSpinBox()
        self.max_input.setRange(-1_000_000, 1_000_000)
        self.max_input.setValue(1023.0)
        self.max_input.setDecimals(2)

        self.std_limit_input = QDoubleSpinBox()
        self.std_limit_input.setRange(0.0, 1_000_000)
        self.std_limit_input.setValue(5.0)
        self.std_limit_input.setDecimals(2)

        self.visibility_min_input = QDoubleSpinBox()
        self.visibility_min_input.setRange(0.0, 1.0)
        self.visibility_min_input.setSingleStep(0.01)
        self.visibility_min_input.setValue(0.20)
        self.visibility_min_input.setDecimals(3)

        self.baseline_points_input = QSpinBox()
        self.baseline_points_input.setRange(20, 500)
        self.baseline_points_input.setValue(200)

        self.calibration_note = QLabel("Calibration: Manual")

        calibrate_layout.addWidget(QLabel("Min Expected"), 0, 0)
        calibrate_layout.addWidget(self.min_input, 0, 1)
        calibrate_layout.addWidget(QLabel("Max Expected"), 0, 2)
        calibrate_layout.addWidget(self.max_input, 0, 3)
        calibrate_layout.addWidget(QLabel("Max Std Dev"), 1, 0)
        calibrate_layout.addWidget(self.std_limit_input, 1, 1)
        calibrate_layout.addWidget(QLabel("Min Visibility"), 1, 2)
        calibrate_layout.addWidget(self.visibility_min_input, 1, 3)
        calibrate_layout.addWidget(QLabel("Baseline Points"), 2, 0)
        calibrate_layout.addWidget(self.baseline_points_input, 2, 1)
        calibrate_layout.addWidget(self.calibration_note, 2, 2, 1, 2)

        calibrate_box.setLayout(calibrate_layout)
        self.layout.addWidget(calibrate_box)

        # KPI row
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)

        self.kpi_current = self.create_kpi_card("Current", "0.00")
        self.kpi_mean = self.create_kpi_card("Mean", "0.00")
        self.kpi_std = self.create_kpi_card("Std Dev", "0.00")
        self.kpi_peak = self.create_kpi_card("Peak-to-Peak", "0.00")
        self.kpi_visibility = self.create_kpi_card("Visibility", "0.000")
        self.kpi_rms = self.create_kpi_card("RMS", "0.00")
        self.kpi_health = self.create_kpi_card("Health Score", "100")

        kpi_cards = [
            self.kpi_current,
            self.kpi_mean,
            self.kpi_std,
            self.kpi_peak,
            self.kpi_visibility,
            self.kpi_rms,
            self.kpi_health,
        ]
        for i, card in enumerate(kpi_cards):
            kpi_grid.addWidget(card, 0, i)

        self.layout.addLayout(kpi_grid)

        # Analysis row (live + histogram + fingerprint)
        content_row = QHBoxLayout()
        content_row.setSpacing(10)

        self.live_plot = pg.PlotWidget()
        self.live_plot.setBackground("#ffffff")
        self.live_plot.setTitle("Live Signal")
        self.live_plot.showGrid(x=True, y=True, alpha=0.2)
        self.live_curve = self.live_plot.plot(pen=pg.mkPen(color="#2563eb", width=2))
        self.lower_limit_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#f59e0b", width=1, style=pg.QtCore.Qt.DashLine))
        self.upper_limit_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#f59e0b", width=1, style=pg.QtCore.Qt.DashLine))
        self.live_plot.addItem(self.lower_limit_line)
        self.live_plot.addItem(self.upper_limit_line)

        self.hist_plot = pg.PlotWidget()
        self.hist_plot.setBackground("#ffffff")
        self.hist_plot.setTitle("Distribution")
        self.hist_plot.showGrid(x=True, y=True, alpha=0.2)
        self.hist_bar = pg.BarGraphItem(x=[], height=[], width=1, brush="#16a34a")
        self.hist_plot.addItem(self.hist_bar)

        self.fft_plot = pg.PlotWidget()
        self.fft_plot.setBackground("#ffffff")
        self.fft_plot.setTitle("Finger Analysis (Frequency Signature)")
        self.fft_plot.showGrid(x=True, y=True, alpha=0.2)
        self.fft_curve = self.fft_plot.plot(pen=pg.mkPen(color="#dc2626", width=2))

        content_row.addWidget(self.live_plot, 2)
        content_row.addWidget(self.hist_plot, 1)
        content_row.addWidget(self.fft_plot, 1)
        self.layout.addLayout(content_row)

        # Finger analytics summary
        finger_box = QGroupBox("Finger Analytics Summary")
        finger_layout = QGridLayout()
        self.finger_trend = QLabel("Trend: Flat")
        self.finger_stability = QLabel("Stability: Unknown")
        self.finger_signal_quality = QLabel("Signal Quality: Unknown")
        self.finger_dominant = QLabel("Dominant Frequency Bin: 0")
        self.alert_state = QLabel("Alert: Waiting for data")
        self.alert_state.setObjectName("alertWarn")
        finger_layout.addWidget(self.finger_trend, 0, 0)
        finger_layout.addWidget(self.finger_stability, 0, 1)
        finger_layout.addWidget(self.finger_signal_quality, 1, 0)
        finger_layout.addWidget(self.finger_dominant, 1, 1)
        finger_layout.addWidget(self.alert_state, 2, 0, 1, 2)
        finger_box.setLayout(finger_layout)
        self.layout.addWidget(finger_box)

        # Alert event log table
        alerts_box = QGroupBox("Alert Event Log")
        alerts_layout = QVBoxLayout()
        self.alert_table = QTableWidget(0, 6)
        self.alert_table.setHorizontalHeaderLabels([
            "Time",
            "Level",
            "Health",
            "Current",
            "Std Dev",
            "Visibility",
        ])
        self.alert_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.alert_table.setEditTriggers(QTableWidget.NoEditTriggers)
        alerts_layout.addWidget(self.alert_table)
        alerts_box.setLayout(alerts_layout)
        self.layout.addWidget(alerts_box)

        self.setLayout(self.layout)

        self.data = deque(maxlen=500)
        self.recording = False
        self.alert_events = deque(maxlen=250)
        self.last_alert_level = "unknown"
        self.latest_metrics = {}

        # Connections
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.save_btn.clicked.connect(self.save_csv)
        self.export_btn.clicked.connect(self.export_report)
        self.auto_calibrate_btn.clicked.connect(self.auto_calibrate)

        # Timer
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_stream)

    def create_kpi_card(self, title, value):
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(12, 10, 12, 10)

        title_label = QLabel(title)
        title_label.setObjectName("kpiTitle")
        value_label = QLabel(value)
        value_label.setObjectName("kpiValue")

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card.setLayout(card_layout)

        # Keep reference for updates
        card.value_label = value_label
        return card

    def start(self):
        if ser is None:
            self.status_label.setText("Status: Serial not available")
            return
        self.recording = True
        self.timer.start(20)
        self.status_label.setText(f"Status: Recording from {SERIAL_PORT}")

    def stop(self):
        self.recording = False
        self.timer.stop()
        if ser is None:
            self.status_label.setText("Status: Disconnected")
        else:
            self.status_label.setText("Status: Connected")

    def calculate_metrics(self, arr):
        current = float(arr[-1])
        mean_v = float(np.mean(arr))
        std_v = float(np.std(arr))
        min_v = float(np.min(arr))
        max_v = float(np.max(arr))
        peak_to_peak = float(max_v - min_v)
        rms_v = float(np.sqrt(np.mean(np.square(arr))))
        denom = max_v + min_v
        visibility = (max_v - min_v) / denom if abs(denom) > 1e-9 else 0.0
        slope = float(np.polyfit(np.arange(arr.size), arr, 1)[0])

        trend = "Rising" if slope > 0.02 else "Falling" if slope < -0.02 else "Flat"
        stability = "Stable" if std_v < max(1.0, abs(mean_v) * 0.08) else "Variable"
        if std_v < 2:
            signal_quality = "High"
        elif std_v < 5:
            signal_quality = "Moderate"
        else:
            signal_quality = "Noisy"

        centered = arr - mean_v
        fft_mag = np.abs(np.fft.rfft(centered))
        dominant_idx = int(np.argmax(fft_mag[1:]) + 1) if len(fft_mag) > 1 else 0

        return {
            "current": current,
            "mean": mean_v,
            "std": std_v,
            "min": min_v,
            "max": max_v,
            "peak_to_peak": peak_to_peak,
            "rms": rms_v,
            "visibility": visibility,
            "slope": slope,
            "trend": trend,
            "stability": stability,
            "quality": signal_quality,
            "fft_mag": fft_mag,
            "dominant_bin": dominant_idx,
        }

    def update_stream(self):
        if self.recording:
            try:
                raw_value = ser.readline().decode(errors='ignore').strip()
                if raw_value:
                    value = float(raw_value)
                    self.data.append(value)
                    arr = np.array(self.data, dtype=float)

                    if arr.size < 2:
                        self.live_curve.setData(arr)
                        return

                    metrics = self.calculate_metrics(arr)

                    self.kpi_current.value_label.setText(f"{metrics['current']:.2f}")
                    self.kpi_mean.value_label.setText(f"{metrics['mean']:.2f}")
                    self.kpi_std.value_label.setText(f"{metrics['std']:.2f}")
                    self.kpi_peak.value_label.setText(f"{metrics['peak_to_peak']:.2f}")
                    self.kpi_visibility.value_label.setText(f"{metrics['visibility']:.3f}")
                    self.kpi_rms.value_label.setText(f"{metrics['rms']:.2f}")

                    min_expected = self.min_input.value()
                    max_expected = self.max_input.value()
                    std_limit = self.std_limit_input.value()
                    min_visibility = self.visibility_min_input.value()

                    self.lower_limit_line.setValue(min_expected)
                    self.upper_limit_line.setValue(max_expected)

                    # Live curve
                    self.live_curve.setData(arr)

                    # Distribution histogram
                    bins = min(20, max(5, int(np.sqrt(arr.size))))
                    hist, edges = np.histogram(arr, bins=bins)
                    centers = (edges[:-1] + edges[1:]) / 2
                    width = (edges[1] - edges[0]) * 0.85 if len(edges) > 1 else 1
                    self.hist_plot.removeItem(self.hist_bar)
                    self.hist_bar = pg.BarGraphItem(x=centers, height=hist, width=width, brush="#16a34a")
                    self.hist_plot.addItem(self.hist_bar)

                    # Frequency fingerprint
                    freq_bins = np.arange(len(metrics['fft_mag']))
                    self.fft_curve.setData(freq_bins, metrics['fft_mag'])

                    self.finger_trend.setText(
                        f"Trend: {metrics['trend']} (slope={metrics['slope']:.4f})"
                    )
                    self.finger_stability.setText(f"Stability: {metrics['stability']}")
                    self.finger_signal_quality.setText(f"Signal Quality: {metrics['quality']}")
                    self.finger_dominant.setText(
                        f"Dominant Frequency Bin: {metrics['dominant_bin']}"
                    )

                    in_range = min_expected <= metrics['current'] <= max_expected
                    stable_std = metrics['std'] <= std_limit
                    good_visibility = metrics['visibility'] >= min_visibility

                    health_score = 100
                    if not in_range:
                        health_score -= 45
                    if not stable_std:
                        health_score -= 30
                    if not good_visibility:
                        health_score -= 25
                    health_score = max(0, health_score)
                    self.kpi_health.value_label.setText(f"{health_score}")

                    if health_score >= 85:
                        alert_level = "normal"
                        self.alert_state.setObjectName("alertOk")
                        self.alert_state.setText("Alert: Normal operation")
                        self.live_plot.setBackground("#ffffff")
                    elif health_score >= 60:
                        alert_level = "warning"
                        self.alert_state.setObjectName("alertWarn")
                        self.alert_state.setText("Alert: Warning - monitor drift/noise")
                        self.live_plot.setBackground("#fffbeb")
                    else:
                        alert_level = "critical"
                        self.alert_state.setObjectName("alertBad")
                        self.alert_state.setText("Alert: Critical - out of calibration")
                        self.live_plot.setBackground("#fef2f2")

                    self.latest_metrics = {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "current": metrics['current'],
                        "mean": metrics['mean'],
                        "std": metrics['std'],
                        "peak_to_peak": metrics['peak_to_peak'],
                        "visibility": metrics['visibility'],
                        "rms": metrics['rms'],
                        "health": health_score,
                        "trend": metrics['trend'],
                        "stability": metrics['stability'],
                        "quality": metrics['quality'],
                        "dominant_bin": metrics['dominant_bin'],
                        "alert_level": alert_level,
                    }

                    if alert_level != self.last_alert_level:
                        self.log_alert_event(alert_level, health_score, metrics)
                        self.last_alert_level = alert_level

                    # Refresh style when object name changes dynamically.
                    self.alert_state.style().unpolish(self.alert_state)
                    self.alert_state.style().polish(self.alert_state)
            except Exception:
                pass

    def log_alert_event(self, level, health_score, metrics):
        event = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "health": int(health_score),
            "current": float(metrics['current']),
            "std": float(metrics['std']),
            "visibility": float(metrics['visibility']),
        }
        self.alert_events.appendleft(event)
        self.refresh_alert_table()

    def refresh_alert_table(self):
        self.alert_table.setRowCount(len(self.alert_events))
        for row, event in enumerate(self.alert_events):
            self.alert_table.setItem(row, 0, QTableWidgetItem(event["time"]))
            self.alert_table.setItem(row, 1, QTableWidgetItem(event["level"].upper()))
            self.alert_table.setItem(row, 2, QTableWidgetItem(str(event["health"])))
            self.alert_table.setItem(row, 3, QTableWidgetItem(f"{event['current']:.2f}"))
            self.alert_table.setItem(row, 4, QTableWidgetItem(f"{event['std']:.2f}"))
            self.alert_table.setItem(row, 5, QTableWidgetItem(f"{event['visibility']:.3f}"))

    def auto_calibrate(self):
        points = self.baseline_points_input.value()
        if len(self.data) < points:
            self.calibration_note.setText(f"Calibration: Need at least {points} points")
            return

        arr = np.array(list(self.data)[-points:], dtype=float)
        mean_v = float(np.mean(arr))
        std_v = float(np.std(arr))
        min_v = float(np.min(arr))
        max_v = float(np.max(arr))

        metrics = self.calculate_metrics(arr)

        margin = max(0.5, std_v * 0.75)
        min_expected = min_v - margin
        max_expected = max_v + margin
        std_limit = max(1.0, std_v * 1.4)
        visibility_min = max(0.02, metrics['visibility'] * 0.70)

        self.min_input.setValue(min_expected)
        self.max_input.setValue(max_expected)
        self.std_limit_input.setValue(std_limit)
        self.visibility_min_input.setValue(min(1.0, visibility_min))

        self.calibration_note.setText(
            f"Calibration: Auto updated ({points} pts, mean={mean_v:.2f}, std={std_v:.2f})"
        )

    def export_report(self):
        base_path, _ = QFileDialog.getSaveFileName(self, "Export Report Base Name", "analyzer_report", "CSV Files (*.csv)")
        if not base_path:
            return

        if base_path.lower().endswith(".csv"):
            base_path = base_path[:-4]

        data_path = f"{base_path}_data.csv"
        alert_path = f"{base_path}_alerts.csv"
        summary_path = f"{base_path}_summary.txt"

        with open(data_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["index", "value"])
            for idx, val in enumerate(self.data):
                writer.writerow([idx, f"{float(val):.6f}"])

        with open(alert_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "level", "health", "current", "std", "visibility"])
            for event in self.alert_events:
                writer.writerow([
                    event["time"],
                    event["level"],
                    event["health"],
                    f"{event['current']:.6f}",
                    f"{event['std']:.6f}",
                    f"{event['visibility']:.6f}",
                ])

        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("Interferometer Pro Analyzer Report\n")
            f.write("=" * 38 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Serial Port: {SERIAL_PORT}\n")
            f.write(f"Samples Stored: {len(self.data)}\n")
            f.write(f"Alert Events Stored: {len(self.alert_events)}\n\n")

            f.write("Calibration Limits\n")
            f.write("-" * 20 + "\n")
            f.write(f"Min Expected: {self.min_input.value():.3f}\n")
            f.write(f"Max Expected: {self.max_input.value():.3f}\n")
            f.write(f"Max Std Dev: {self.std_limit_input.value():.3f}\n")
            f.write(f"Min Visibility: {self.visibility_min_input.value():.3f}\n\n")

            f.write("Latest Metrics\n")
            f.write("-" * 20 + "\n")
            if self.latest_metrics:
                for key, value in self.latest_metrics.items():
                    f.write(f"{key}: {value}\n")
            else:
                f.write("No live metrics captured yet.\n")

            f.write("\nOutput Files\n")
            f.write("-" * 20 + "\n")
            f.write(f"Data CSV: {data_path}\n")
            f.write(f"Alerts CSV: {alert_path}\n")
            f.write(f"Summary: {summary_path}\n")

        self.status_label.setText(f"Status: Report exported -> {base_path}")

    def save_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if file_path:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["index", "value"])
                for idx, val in enumerate(self.data):
                    writer.writerow([idx, f"{float(val):.6f}"])

app = QApplication(sys.argv)
window = Dashboard()
window.show()
sys.exit(app.exec_())
