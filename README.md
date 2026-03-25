# Interferometer Pro Analyzer

A real-time desktop dashboard for monitoring and analyzing optical interferometer signals over a serial connection. Built with PyQt5 and pyqtgraph.

---

## Features

- Live signal plot with configurable threshold lines
- Distribution histogram updated in real time
- Frequency fingerprint (FFT) of the incoming signal
- KPI cards: Current, Mean, Std Dev, Peak-to-Peak, Visibility, RMS, Health Score
- Auto-calibration from a rolling baseline window
- Alert system with three levels: Normal, Warning, Critical
- Alert event log table with timestamps
- CSV data export and full text report export

---

## Requirements

- Python 3.9 or higher
- A serial device sending numeric values (one per line) at 9600 baud
- Windows / macOS / Linux

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Setup

1. Connect your interferometer or sensor to a serial/USB port.
2. Open `modern_dashboard.py` and update the port at the top:

```python
SERIAL_PORT = 'COM15'   # Windows example
# SERIAL_PORT = '/dev/ttyUSB0'  # Linux example
# SERIAL_PORT = '/dev/tty.usbmodem14101'  # macOS example
BAUD_RATE = 9600
```

3. Run the dashboard:

```bash
python modern_dashboard.py
```

---

## Serial Data Format

The dashboard expects the serial device to send one numeric value per line, e.g.:

```
512.00
513.45
510.88
...
```

Any non-numeric lines are silently ignored.

---

## Usage

### Controls

| Button | Action |
|---|---|
| Start | Begin reading from the serial port |
| Stop | Pause reading |
| Save CSV | Save raw signal data to a CSV file |
| Export Report | Export data CSV, alert log CSV, and a summary text file |
| Auto Calibrate | Compute thresholds automatically from recent data |

### Calibration and Thresholds

| Field | Description |
|---|---|
| Min / Max Expected | Expected signal range; values outside trigger health penalty |
| Max Std Dev | Noise limit; exceeding this reduces health score |
| Min Visibility | Minimum acceptable fringe visibility (0–1) |
| Baseline Points | Number of recent samples used for auto-calibration |

### Health Score

Computed each tick from three checks:

| Condition | Penalty |
|---|---|
| Signal out of expected range | −45 |
| Std dev exceeds limit | −30 |
| Visibility below minimum | −25 |

| Score | Alert Level |
|---|---|
| ≥ 85 | Normal (green) |
| 60 – 84 | Warning (amber) |
| < 60 | Critical (red) |

---

## Exported Files

When you click "Export Report", three files are created using the base name you choose:

- `<name>_data.csv` — raw signal samples
- `<name>_alerts.csv` — alert event log with timestamps
- `<name>_summary.txt` — calibration settings and latest metrics

---

## Project Structure

```
.
├── modern_dashboard.py   # Main application
├── requirements.txt      # Python dependencies
└── README.md
```

---

## Troubleshooting

**Serial port not found**
- Verify the port name in `SERIAL_PORT` matches your device manager / `ls /dev/tty*`
- Make sure no other application is holding the port open

**No data appearing after Start**
- Check baud rate matches your device (default 9600)
- Confirm the device is sending plain numeric lines terminated with `\n`

**PyQt5 install fails on Linux**
- Try `sudo apt install python3-pyqt5` as an alternative to pip
