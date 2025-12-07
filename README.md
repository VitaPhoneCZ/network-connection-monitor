# 🌐 Network Connection Monitor

[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![No Dependencies](https://img.shields.io/badge/Dependencies-None-brightgreen.svg)]()

A high-frequency network connection monitoring tool that tests TCP connectivity and tracks packet loss, latency, and connection outages over time. Perfect for diagnosing intermittent network issues, monitoring ISP quality, or testing server availability.

---

## 📋 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Configuration](#%EF%B8%8F-configuration)
- [Output Files](#-output-files)
- [Console Output](#-console-output)
- [How It Works](#-how-it-works)
- [Use Cases](#-use-cases)
- [Example Output](#-example-output)
- [Building from Source](#-building-from-source)
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚀 **High-frequency testing** | Up to 1000 tests per second (1ms interval) for precise measurements |
| 📉 **Packet loss detection** | Automatically identifies and logs periods of significant packet loss |
| ⏱️ **Latency tracking** | Measures and records RTT (Round Trip Time) for each connection attempt |
| 🛑 **Graceful shutdown** | Press Ctrl+C once for clean shutdown, twice for immediate exit |
| 💾 **RAM management** | Automatic cleanup of old data to prevent memory issues during long runs |
| 📊 **Multi-level aggregation** | Statistics aggregated per second, minute, and hour |
| 📁 **Session-based logging** | Each run creates a timestamped folder with all logs |
| 🔧 **Zero dependencies** | Standalone executable - no Python installation required |

---

## 📦 Requirements

### For the Executable (Recommended)
- **Windows 10/11** (64-bit)
- No Python installation required
- No dependencies

### For the Python Script
- **Python 3.6** or higher
- No external dependencies (uses only Python standard library)

---

## 🔧 Installation

### Option 1: Download Executable (Recommended) ⭐

1. Go to the [Releases](https://github.com/VitaPhoneCZ/network-connection-monitor/releases) page
2. Download the latest `NetworkMonitor.exe`
3. Place it in any folder
4. Double-click to run!

> 💡 **Note:** The full Python source code ([`network_monitor.py`](network_monitor.py)) is included in the repository, so you can inspect, modify, or learn from the code at any time.

### Option 2: Clone Repository

```bash
git clone https://github.com/VitaPhoneCZ/network-connection-monitor.git
cd network-connection-monitor
```

### Option 3: Download ZIP

1. Go to [https://github.com/VitaPhoneCZ/network-connection-monitor](https://github.com/VitaPhoneCZ/network-connection-monitor)
2. Click the green "Code" button
3. Select "Download ZIP"
4. Extract to your desired location

---

## 🚀 Quick Start

### Using the Executable (Recommended)

```
1. Download NetworkMonitor.exe
2. Double-click NetworkMonitor.exe
3. The monitor starts immediately
4. Press Ctrl+C to stop and save statistics
```

> **Note:** Windows SmartScreen may show a warning on first run. Click "More info" → "Run anyway" to proceed.

### Using Python Script

```bash
python network_monitor.py
```

**What happens when you run it:**

1. Creates a new session folder (e.g., `session_20251207_165602/`)
2. Starts testing TCP connections at high frequency
3. Displays real-time statistics every 10 seconds
4. On shutdown, saves all statistics and displays a summary

---

## ⚙️ Configuration

> **Note:** To change configuration when using the executable, you need to edit the Python script and rebuild the exe, or use the Python script directly.

Edit the configuration section at the top of `network_monitor.py`:

```python
# ============== CONFIGURATION ==============
host = '1.1.1.1'              # Target host (Cloudflare DNS)
port = 53                      # Target port (DNS)
interval = 0.001               # Test interval in seconds (1ms)
timeout = 0.025                # Connection timeout in seconds (25ms)
PACKET_LOSS_THRESHOLD = 0.3    # Packet loss threshold (30%)
SAVE_CONNECTION_LOG = False    # Enable/disable detailed logging
FILE_WRITE_INTERVAL = 10       # Statistics update interval (seconds)
MAX_SECONDS_IN_MEMORY = 3600   # RAM limit: seconds of data to keep
# ==========================================
```

### Configuration Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `host` | `'1.1.1.1'` | Any valid IP/hostname | Target host to monitor. Cloudflare DNS is reliable and fast. |
| `port` | `53` | 1-65535 | Target port. Port 53 (DNS) is commonly open. |
| `interval` | `0.001` | 0.001-60 | Time between tests in seconds. Lower = more precise but higher CPU. |
| `timeout` | `0.025` | 0.001-30 | Connection timeout. Should be less than interval. |
| `PACKET_LOSS_THRESHOLD` | `0.3` | 0.0-1.0 | Packet loss ratio to consider as "outage" (0.3 = 30%). |
| `SAVE_CONNECTION_LOG` | `False` | True/False | Log every single connection attempt. ⚠️ Creates large files! |
| `FILE_WRITE_INTERVAL` | `10` | 1-3600 | How often to update statistics files (seconds). |
| `MAX_SECONDS_IN_MEMORY` | `3600` | 60-86400 | Seconds of per-second data to keep in RAM. Older data is purged. |

### Recommended Configurations

**For general ISP monitoring:**
```python
interval = 0.1      # 10 tests per second
timeout = 0.05      # 50ms timeout
```

**For detecting micro-outages:**
```python
interval = 0.001    # 1000 tests per second (default)
timeout = 0.025     # 25ms timeout
```

**For long-term monitoring (24h+):**
```python
MAX_SECONDS_IN_MEMORY = 7200  # Keep 2 hours in RAM
FILE_WRITE_INTERVAL = 60       # Update files every minute
```

---

## 📁 Output Files

Each session creates a timestamped folder with the following files:

```
session_20251207_165602/
├── session_20251207_165602.txt    # Session summary
├── averages_per_second.txt        # Per-second statistics
├── averages_per_minute.txt        # Per-minute aggregated stats
├── averages_per_hour.txt          # Per-hour aggregated stats
├── packetloss.txt                 # Detailed outage log
└── connection_log.txt             # Individual results (if enabled)
```

### File Descriptions

| File | Size | Description |
|------|------|-------------|
| `session_*.txt` | ~1 KB | Session configuration and final statistics summary |
| `averages_per_second.txt` | ~100 KB/hour | Detailed per-second statistics with sent/received/RTT |
| `averages_per_minute.txt` | ~2 KB/hour | Aggregated per-minute statistics |
| `averages_per_hour.txt` | ~100 bytes/hour | Aggregated per-hour statistics |
| `packetloss.txt` | Variable | List of detected packet loss outages with timestamps |
| `connection_log.txt` | ~50 MB/hour | Every single connection result (only if `SAVE_CONNECTION_LOG=True`) |

> ⚠️ **Warning:** Enabling `SAVE_CONNECTION_LOG` generates approximately 50MB of data per hour at default settings.

---

## 🖥️ Console Output

The program displays real-time statistics in the console:

```
Monitoring started. Press Ctrl+C to stop.
Packet loss threshold: 30%
Session folder: session_20251207_165602
Statistics update every 10 seconds.
RAM management: keeping last 3600 seconds in memory.
------------------------------------------------------------------------------------------------------------------------
Time range (10s)             Sent         Received     Avg RTT (ms)       Success      Failed       Outage
------------------------------------------------------------------------------------------------------------------------
2025-12-07 16:56:02 - 16:56:11    285          285          12.45              285          0            No
2025-12-07 16:56:12 - 16:56:21    290          288          13.21              288          2            No
2025-12-07 16:56:22 - 16:56:31    287          142          45.67              142          145          Yes
```

### Column Descriptions

| Column | Description |
|--------|-------------|
| **Time range** | 10-second window being displayed |
| **Sent** | Number of connection attempts |
| **Received** | Number of successful connections |
| **Avg RTT** | Average round-trip time in milliseconds |
| **Success** | Number of successful tests |
| **Failed** | Number of failed tests |
| **Outage** | "Yes" if packet loss exceeds threshold |

---

## 🔄 How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    Network Connection Monitor                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   1. TCP Connection Test                                          │
│      ┌──────────┐    SYN     ┌──────────┐                        │
│      │  Script  │ ────────► │  Target  │                        │
│      │          │ ◄──────── │  Host    │                        │
│      └──────────┘  SYN-ACK  └──────────┘                        │
│           │                                                       │
│           │ Measure RTT                                           │
│           ▼                                                       │
│   2. Data Aggregation                                             │
│      ┌─────────────┬─────────────┬─────────────┐                 │
│      │ Per Second  │ Per Minute  │  Per Hour   │                 │
│      └─────────────┴─────────────┴─────────────┘                 │
│           │                                                       │
│           ▼                                                       │
│   3. Outage Detection                                             │
│      If packet_loss > threshold → Log outage                      │
│           │                                                       │
│           ▼                                                       │
│   4. Periodic File Writes                                         │
│      Every N seconds → Update all statistics files                │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Technical Details

1. **TCP Socket Connection**: Creates a new TCP socket for each test, attempts to connect, measures the time, then closes the socket.

2. **High-Frequency Testing**: At 1ms interval, the script can perform ~1000 tests per second, allowing detection of brief outages.

3. **RAM Management**: To prevent memory exhaustion during long runs, old per-second data is automatically purged after `MAX_SECONDS_IN_MEMORY` seconds.

4. **Graceful Shutdown**: Uses signal handlers to catch Ctrl+C and complete the current cycle before saving final statistics.

---

## 🎯 Use Cases

### 1. ISP Quality Monitoring
Track your internet connection stability over extended periods. Useful for documenting issues to report to your ISP.

### 2. Network Troubleshooting
Identify intermittent connection issues that are hard to catch manually. The high-frequency testing can detect sub-second outages.

### 3. Server Availability Testing
Monitor uptime of critical services. Change the `host` and `port` to point to your server.

### 4. Latency Analysis
Analyze RTT patterns and spikes. Useful for gaming, VoIP, or real-time applications.

### 5. Before/After Comparison
Run the monitor before and after network changes to quantify improvements.

---

## 📊 Example Output

### Session Summary (`session_*.txt`)

```
Session started: 2025-12-07 16:56:02.123
Host: 1.1.1.1
Port: 53
Interval: 0.001 seconds
Connection log: Disabled
Packet loss threshold: 30.0%
Max seconds in memory: 3600
================================================================================

================================================================================
Session ended: 2025-12-07 17:11:34.456
================================================================================

TOTAL STATISTICS:
----------------------------------------
Duration:         0:15:32
Sent:             45892 packets
Received:         45890 packets
Lost:             2 packets (0.00%)
Average RTT:      12.34 ms
Packet loss outages: 0
```

### Packet Loss Report (`packetloss.txt`)

```
Packet loss outages - 2 outages
====================================================================================================

Outage #1:
  From: 2025-12-07 16:58:23
  To: 2025-12-07 16:58:25
  Duration: 3 seconds
  Sent: 892 | Received: 234 | Loss: 73.8%
----------------------------------------------------------------------------------------------------
Outage #2:
  From: 2025-12-07 17:05:11
  To: 2025-12-07 17:05:11
  Duration: 1 second
  Sent: 298 | Received: 145 | Loss: 51.3%
----------------------------------------------------------------------------------------------------
```

---

## 🔨 Building from Source

The complete source code is always available in the repository ([`network_monitor.py`](network_monitor.py)). If you want to build the executable yourself, make modifications, or simply prefer running Python scripts:

### Prerequisites

```bash
pip install pyinstaller
```

### Build Command

```bash
pyinstaller --onefile --console --name "NetworkMonitor" network_monitor.py
```

### Output

The executable will be created in the `dist/` folder:
```
dist/
└── NetworkMonitor.exe
```

### Build Options

| Option | Description |
|--------|-------------|
| `--onefile` | Create a single executable file |
| `--console` | Keep console window (required for this app) |
| `--name "NAME"` | Set the output filename |
| `--icon icon.ico` | Add a custom icon (optional) |

---

## 🔧 Troubleshooting

### Common Issues

**Problem: Windows SmartScreen blocks the executable**
```
Solution: Click "More info" → "Run anyway". The exe is not signed, so Windows
shows this warning for any unsigned executable.
```

**Problem: "Permission denied" or connection refused**
```
Solution: Try a different port or host. Port 53 might be blocked on some networks.
Alternative hosts: 8.8.8.8 (Google DNS), 208.67.222.222 (OpenDNS)
```

**Problem: Very high packet loss even with good connection**
```
Solution: Increase the timeout value. Some networks have higher latency.
Edit the script: timeout = 0.1  # Try 100ms timeout
```

**Problem: Script uses too much CPU**
```
Solution: Increase the interval between tests.
Edit the script: interval = 0.01  # 100 tests per second instead of 1000
```

**Problem: Running out of memory during long sessions**
```
Solution: Decrease MAX_SECONDS_IN_MEMORY
Edit the script: MAX_SECONDS_IN_MEMORY = 1800  # Keep only 30 minutes
```

**Problem: Antivirus flags the executable**
```
Solution: This is a false positive common with PyInstaller executables.
Add an exception in your antivirus, or run the Python script directly.
```

### Platform-Specific Notes

**Windows:**
- The executable is built for Windows 64-bit
- Run as Administrator if you experience permission issues
- Windows Defender might briefly slow down the first run

**Linux/macOS:**
- Use the Python script directly
- No special permissions needed for TCP connections
- For ports below 1024, you might need sudo

---

## ❓ FAQ

**Q: Why TCP instead of ICMP ping?**
> A: TCP doesn't require elevated privileges and works through most firewalls. ICMP is often blocked or rate-limited.

**Q: Can I monitor multiple hosts?**
> A: Currently, no. Run multiple instances with different configurations for multiple hosts.

**Q: How accurate is the RTT measurement?**
> A: The measurement includes TCP handshake time (SYN → SYN-ACK). It's slightly higher than ICMP ping but more representative of real application behavior.

**Q: Will this affect my network performance?**
> A: The bandwidth usage is negligible (a few KB/s). However, very high frequency testing might trigger rate limiting on some networks.

**Q: Can I use this commercially?**
> A: Yes, the MIT license allows commercial use.

**Q: Why is the executable so large (~5MB)?**
> A: PyInstaller bundles the Python interpreter and all required libraries into a single file for portability.

**Q: Can I change settings without rebuilding the exe?**
> A: Not currently. For custom settings, use the Python script directly or rebuild the executable.

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

### Ideas for Contributions

- [ ] Add command-line arguments for configuration
- [ ] Add UDP testing support
- [ ] Create a web dashboard for real-time monitoring
- [ ] Add email/webhook alerts for outages
- [ ] Support for multiple hosts
- [ ] Export to CSV/JSON formats
- [ ] Graphical charts generation
- [ ] Linux/macOS executable builds

---

## 📄 License

This project is licensed under the MIT License - see below for details:

```
MIT License

Copyright (c) 2025 VitaPhoneCZ

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## ⭐ Star History

If you find this tool useful, please consider giving it a star on GitHub!

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/VitaPhoneCZ">VitaPhoneCZ</a>
</p>
