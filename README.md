# 🌐 Network Connection Monitor

[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

A high-frequency network monitoring tool with real-time web dashboard, multi-host support, and alerting capabilities. Perfect for diagnosing intermittent network issues, monitoring ISP quality, or testing server availability.

![Dashboard Preview](https://img.shields.io/badge/Web_Dashboard-Live_Charts-00d9ff?style=for-the-badge)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚀 **High-frequency testing** | Up to 1000 tests/second (1ms interval) for precise measurements |
| 🌐 **Web Dashboard** | Real-time browser-based monitoring with live charts |
| 📈 **Interactive Charts** | RTT and packet loss graphs with Live/Minute/Hour modes |
| 📡 **TCP & UDP Support** | Test both protocols |
| 🖥️ **Multi-host monitoring** | Monitor multiple servers simultaneously |
| 🚨 **Outage Detection** | Automatic detection and logging of network outages |
| 📤 **CSV/JSON Export** | Export data for external analysis |
| 🔔 **Alerts** | Email and webhook notifications for outages |
| 💾 **RAM Management** | Automatic cleanup for long-running sessions |
| 🛑 **Graceful shutdown** | Clean exit with Ctrl+C, saves all data |

---

## 🚀 Quick Start

### Option 1: Download Executable (Recommended)

1. Download `NetworkMonitor.exe` from [Releases](https://github.com/VitaPhoneCZ/network-connection-monitor/releases)
2. Double-click to run — web dashboard opens automatically!

Or run with custom options:
```bash
NetworkMonitor.exe -H 1.1.1.1:53 8.8.8.8:53 google.com:443 --web
```

### Option 2: Run from Python

```bash
# Install dependencies
pip install flask

# Run (web dashboard opens automatically)
python network_monitor.py
```

---

## 📖 Command-Line Options

```
Usage: network_monitor.py [OPTIONS]

Host Configuration:
  -H, --hosts           Hosts to monitor (format: host:port/protocol)
                        Examples: 1.1.1.1:53  8.8.8.8:53/udp  google.com:443/tcp

Timing:
  -i, --interval        Test interval in seconds (default: 0.001 = 1ms)
  -t, --timeout         Connection timeout in seconds (default: 0.025 = 25ms)
  --threshold           Packet loss threshold for outage (default: 0.3 = 30%)
  --write-interval      How often to save stats to files (default: 10s)
  --max-seconds         Seconds of data to keep in RAM (default: 3600 = 1 hour)

Output:
  --csv                 Export data to CSV format
  --json                Export data to JSON format
  --charts              Generate PNG charts on exit (requires matplotlib)

Web Dashboard:
  --web                 Enable web dashboard (auto-opens browser)
  --web-port            Dashboard port (default: 5000)

Alerts:
  --webhook URL         Webhook URL for alerts (Slack, Discord, etc.)
  --email-to            Email address for alerts
  --smtp-host           SMTP server (default: smtp.gmail.com)
  --smtp-port           SMTP port (default: 587)
  --email-user          SMTP username
  --email-pass          SMTP password
  --alert-cooldown      Seconds between alerts for same host (default: 300)
```

---

## 💡 Examples

```bash
# Basic: Monitor Cloudflare DNS (opens web dashboard)
NetworkMonitor.exe

# Monitor multiple hosts
NetworkMonitor.exe -H 1.1.1.1:53 8.8.8.8:53 google.com:443

# Custom port for web dashboard
NetworkMonitor.exe -H 1.1.1.1:53 --web-port 8080

# Lower frequency monitoring (10 tests/sec instead of 1000)
NetworkMonitor.exe -H 1.1.1.1:53 -i 0.1 -t 0.5

# Export to CSV and JSON
NetworkMonitor.exe -H 1.1.1.1:53 --csv --json

# With Slack webhook alerts
NetworkMonitor.exe -H 1.1.1.1:53 --webhook https://hooks.slack.com/services/xxx

# With email alerts
NetworkMonitor.exe -H 1.1.1.1:53 \
    --email-to alerts@example.com \
    --email-user sender@gmail.com \
    --email-pass "app-password"

# UDP testing
NetworkMonitor.exe -H 8.8.8.8:53/udp
```

---

## 🖥️ Web Dashboard

The web dashboard provides real-time monitoring with:

- **Live Statistics**: Packets sent/received, packet loss %, average RTT
- **Interactive Charts**: RTT and packet loss over time
  - **Live mode**: Real-time updates (last 2 minutes)
  - **Minute mode**: Per-minute aggregated data
  - **Hour mode**: Per-hour aggregated data
- **Host Status Table**: Status, RTT, and success rate for each host
- **Outage Log**: Recent outages with timestamps and details

Charts support hover tooltips showing exact values.

---

## 📁 Output Files

Each session creates a timestamped folder:

```
session_20251207_165602/
├── session.txt                    # Session info
├── outages.txt                    # Detected outages
└── 1.1.1.1_53_tcp/               # Per-host folder
    ├── per_second.txt            # Per-second statistics
    ├── per_minute.txt            # Per-minute statistics
    ├── data.csv                  # If --csv enabled
    ├── data.json                 # If --json enabled
    ├── rtt_chart.png             # If --charts enabled
    └── packet_loss.png           # If --charts enabled
```

---

## 🔨 Building from Source

```bash
# Create virtual environment (first time only)
python -m venv .venv
.venv\Scripts\pip install flask pyinstaller

# Build executable
python build.py

# Output: dist/NetworkMonitor.exe (~11 MB)
```

**Note:** PNG chart generation (`--charts`) requires matplotlib, which is not bundled in the exe. Use the Python script directly for this feature.

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Windows SmartScreen warning | Click "More info" → "Run anyway" |
| Permission denied | Try different host/port, or run as admin |
| High packet loss on good connection | Increase `--timeout` (e.g., `-t 0.5`) |
| High CPU usage | Increase `--interval` (e.g., `-i 0.1` for 10 tests/sec) |
| Web dashboard not opening | Check if port 5000 is in use, try `--web-port 8080` |

---

## 📄 License

MIT License - see [LICENSE](./LICENSE)

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/VitaPhoneCZ">VitaPhoneCZ</a>
</p>
