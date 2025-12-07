#!/usr/bin/env python3
"""
Network Connection Monitor - Advanced Edition
Supports TCP/UDP testing, multiple hosts, web dashboard, alerts, and more.
"""

import socket
import time
import argparse
import json
import csv
import os
import signal
import threading
import smtplib
import urllib.request
import urllib.error
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

# ============== CONFIGURATION DEFAULTS ==============
DEFAULT_HOSTS = ['1.1.1.1:53']
DEFAULT_INTERVAL = 0.001  # 1ms = ~1000 tests/sec
DEFAULT_TIMEOUT = 0.025   # 25ms timeout
DEFAULT_PACKET_LOSS_THRESHOLD = 0.3
DEFAULT_FILE_WRITE_INTERVAL = 10
DEFAULT_MAX_SECONDS_IN_MEMORY = 3600


@dataclass
class HostConfig:
    host: str
    port: int
    protocol: str = 'tcp'
    name: str = ''
    
    def __post_init__(self):
        if not self.name:
            self.name = f"{self.host}:{self.port}/{self.protocol}"


@dataclass 
class TestResult:
    timestamp: datetime
    host: str
    port: int
    protocol: str
    success: bool
    rtt_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class AggregatedStats:
    sent: int = 0
    received: int = 0
    rtts: List[float] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0
    
    @property
    def avg_rtt(self) -> float:
        return sum(self.rtts) / len(self.rtts) if self.rtts else 0
    
    @property
    def packet_loss(self) -> float:
        return (self.sent - self.received) / self.sent if self.sent > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'sent': self.sent,
            'received': self.received,
            'avg_rtt': self.avg_rtt,
            'success_count': self.success_count,
            'fail_count': self.fail_count,
            'packet_loss': self.packet_loss
        }


class AlertManager:
    def __init__(self, config: Dict[str, Any]):
        self.email_config = config.get('email', {})
        self.webhook_urls = config.get('webhooks', [])
        self.last_alert_time: Dict[str, float] = {}
        self.alert_cooldown = config.get('cooldown', 300)
        
    def should_alert(self, host: str) -> bool:
        now = time.time()
        last = self.last_alert_time.get(host, 0)
        if now - last >= self.alert_cooldown:
            self.last_alert_time[host] = now
            return True
        return False
    
    def send_email_alert(self, subject: str, body: str):
        if not self.email_config.get('enabled'):
            return
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from']
            msg['To'] = self.email_config['to']
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            server = smtplib.SMTP(self.email_config['smtp_host'], self.email_config.get('smtp_port', 587))
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            server.sendmail(self.email_config['from'], self.email_config['to'], msg.as_string())
            server.quit()
            print(f"📧 Email alert sent: {subject}")
        except Exception as e:
            print(f"⚠️ Failed to send email: {e}")
    
    def send_webhook_alert(self, data: Dict[str, Any]):
        for url in self.webhook_urls:
            try:
                payload = json.dumps(data).encode('utf-8')
                req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        print(f"🔔 Webhook sent to {url}")
            except Exception as e:
                print(f"⚠️ Failed to send webhook to {url}: {e}")
    
    def alert_outage(self, host: str, stats: Dict[str, Any]):
        if not self.should_alert(host):
            return
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = f"🚨 Network Outage Detected: {host}"
        body = f"Network outage detected!\n\nHost: {host}\nTime: {timestamp}\nPacket Loss: {stats.get('packet_loss', 0) * 100:.1f}%\n"
        self.send_email_alert(subject, body)
        self.send_webhook_alert({'event': 'outage_detected', 'host': host, 'timestamp': timestamp, 'stats': stats})


class ConnectionTester:
    @staticmethod
    def test_tcp(host: str, port: int, timeout: float) -> TestResult:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            start = time.perf_counter()
            sock.connect((host, port))
            end = time.perf_counter()
            sock.close()
            return TestResult(timestamp=datetime.now(), host=host, port=port, protocol='tcp', success=True, rtt_ms=(end - start) * 1000)
        except Exception as e:
            return TestResult(timestamp=datetime.now(), host=host, port=port, protocol='tcp', success=False, error=str(e))
    
    @staticmethod
    def test_udp(host: str, port: int, timeout: float) -> TestResult:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            start = time.perf_counter()
            sock.sendto(b'\x00', (host, port))
            try:
                sock.recvfrom(1024)
            except socket.timeout:
                pass
            end = time.perf_counter()
            sock.close()
            return TestResult(timestamp=datetime.now(), host=host, port=port, protocol='udp', success=True, rtt_ms=(end - start) * 1000)
        except Exception as e:
            return TestResult(timestamp=datetime.now(), host=host, port=port, protocol='udp', success=False, error=str(e))


class DataExporter:
    @staticmethod
    def to_csv(data: Dict[str, AggregatedStats], filepath: str, time_key: str = 'Time'):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([time_key, 'Sent', 'Received', 'Avg RTT (ms)', 'Success', 'Failed', 'Packet Loss %'])
            for key in sorted(data.keys()):
                stats = data[key]
                writer.writerow([key, stats.sent, stats.received, f"{stats.avg_rtt:.2f}", stats.success_count, stats.fail_count, f"{stats.packet_loss * 100:.2f}"])
    
    @staticmethod
    def to_json(data: Dict[str, AggregatedStats], filepath: str):
        export_data = {key: stats.to_dict() for key, stats in data.items()}
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)
    
    @staticmethod
    def to_txt(data: Dict[str, AggregatedStats], filepath: str, title: str, time_key: str, packet_loss_threshold: float):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{title}:\n{'=' * 100}\n")
            f.write(f"{time_key:<20} {'Sent':<12} {'Received':<12} {'Avg RTT (ms)':<18} {'Success':<12} {'Failed':<12} {'Outage':<10}\n")
            f.write("-" * 100 + "\n")
            for key in sorted(data.keys()):
                stats = data[key]
                outage = stats.packet_loss > packet_loss_threshold
                f.write(f"{key:<20} {stats.sent:<12} {stats.received:<12} {stats.avg_rtt:<18.2f} {stats.success_count:<12} {stats.fail_count:<12} {'Yes' if outage else 'No':<10}\n")


class ChartGenerator:
    def __init__(self, output_dir: str, silent: bool = False):
        self.output_dir = output_dir
        self._matplotlib_available = False
        self._silent = silent
        self.plt = None
        self.mdates = None
    
    def _init_matplotlib(self):
        if self.plt is not None:
            return self._matplotlib_available
        try:
            matplotlib = __import__('matplotlib')
            matplotlib.use('Agg')
            self.plt = __import__('matplotlib.pyplot', fromlist=['pyplot'])
            self.mdates = __import__('matplotlib.dates', fromlist=['dates'])
            self._matplotlib_available = True
        except ImportError:
            if not self._silent:
                print("⚠️ matplotlib not installed. Charts will not be generated.")
        return self._matplotlib_available
    
    def generate_all_charts(self, second_data: Dict[str, AggregatedStats], minute_data: Dict[str, AggregatedStats]):
        if not self._init_matplotlib():
            return
        self._generate_rtt_chart(minute_data, 'rtt_chart.png', 'RTT Over Time')
        self._generate_packet_loss_chart(minute_data, 'packet_loss.png')
        print(f"📊 Charts saved to {self.output_dir}/")
    
    def _generate_rtt_chart(self, data: Dict[str, AggregatedStats], filename: str, title: str):
        if not data or not self.plt:
            return
        times, rtts = [], []
        for key in sorted(data.keys()):
            try:
                times.append(datetime.strptime(key, '%Y-%m-%d %H:%M:%S'))
            except ValueError:
                times.append(datetime.strptime(key, '%Y-%m-%d %H:%M:00'))
            rtts.append(data[key].avg_rtt)
        fig, ax = self.plt.subplots(figsize=(12, 6))
        ax.plot(times, rtts, 'b-', linewidth=1)
        ax.set_xlabel('Time')
        ax.set_ylabel('RTT (ms)')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        fig.savefig(os.path.join(self.output_dir, filename), dpi=150, bbox_inches='tight')
        self.plt.close(fig)
    
    def _generate_packet_loss_chart(self, data: Dict[str, AggregatedStats], filename: str):
        if not data or not self.plt:
            return
        times, losses = [], []
        for key in sorted(data.keys()):
            try:
                times.append(datetime.strptime(key, '%Y-%m-%d %H:%M:%S'))
            except ValueError:
                times.append(datetime.strptime(key, '%Y-%m-%d %H:%M:00'))
            losses.append(data[key].packet_loss * 100)
        fig, ax = self.plt.subplots(figsize=(12, 6))
        ax.bar(times, losses, width=0.0007, color='red', alpha=0.7)
        ax.set_xlabel('Time')
        ax.set_ylabel('Packet Loss (%)')
        ax.set_title('Packet Loss Over Time')
        fig.savefig(os.path.join(self.output_dir, filename), dpi=150, bbox_inches='tight')
        self.plt.close(fig)


class WebDashboard:
    HTML_TEMPLATE = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Network Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#0a0a0f,#1a1a2e);color:#e0e0e0;min-height:100vh;padding:20px}
.container{max-width:1400px;margin:0 auto}
header{display:flex;justify-content:space-between;align-items:center;padding:20px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);border-radius:16px;margin-bottom:20px}
h1{font-size:1.5rem;background:linear-gradient(90deg,#00d9ff,#00ff88);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.status{padding:8px 16px;border-radius:20px;font-size:0.85rem}
.status-ok{background:rgba(0,255,136,0.15);border:1px solid rgba(0,255,136,0.4);color:#00ff88}
.status-error{background:rgba(255,82,82,0.15);border:1px solid rgba(255,82,82,0.4);color:#ff5252}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px}
.card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px}
.card-title{font-size:0.7rem;text-transform:uppercase;color:#888;margin-bottom:8px}
.card-value{font-size:2rem;font-weight:700}
.card-value.info{color:#00d9ff}.card-value.success{color:#00ff88}.card-value.error{color:#ff5252}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
.chart-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px;padding-bottom:30px}
.chart-card h3{font-size:0.8rem;color:#888;margin:0;text-transform:uppercase}
.chart-card canvas{max-height:150px}
.mode-btns{display:flex;gap:5px}
.mode-btn{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);color:#888;padding:4px 10px;border-radius:6px;font-size:0.7rem;cursor:pointer;transition:all 0.2s}
.mode-btn:hover{background:rgba(255,255,255,0.1);color:#fff}
.mode-btn.active{background:rgba(0,217,255,0.2);border-color:rgba(0,217,255,0.4);color:#00d9ff}
table{width:100%;border-collapse:collapse;background:rgba(255,255,255,0.03);border-radius:12px;overflow:hidden}
th,td{padding:12px 16px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.05)}
th{font-size:0.7rem;text-transform:uppercase;color:#666}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:8px}
.dot.on{background:#00ff88;box-shadow:0 0 8px #00ff88}.dot.off{background:#ff5252}
.refresh{text-align:center;padding:15px;color:#555;font-size:0.8rem}
@media(max-width:800px){.charts{grid-template-columns:1fr}}
</style></head>
<body><div class="container">
<header><h1>⚡ Network Monitor</h1><span class="status" id="status">● Loading...</span></header>
<div class="grid">
<div class="card"><div class="card-title">Packets Sent</div><div class="card-value info" id="sent">-</div></div>
<div class="card"><div class="card-title">Packets Received</div><div class="card-value success" id="recv">-</div></div>
<div class="card"><div class="card-title">Packet Loss</div><div class="card-value" id="loss">-</div></div>
<div class="card"><div class="card-title">Average RTT</div><div class="card-value info" id="rtt">-</div></div>
</div>
<div class="charts">
<div class="chart-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><h3>📈 RTT Over Time (ms)</h3><div class="mode-btns" data-chart="rtt"><button class="mode-btn active" data-mode="live">Live</button><button class="mode-btn" data-mode="minute">Minute</button><button class="mode-btn" data-mode="hour">Hour</button></div></div><canvas id="rttChart"></canvas></div>
<div class="chart-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><h3>📉 Packet Loss (%)</h3><div class="mode-btns" data-chart="loss"><button class="mode-btn active" data-mode="live">Live</button><button class="mode-btn" data-mode="minute">Minute</button><button class="mode-btn" data-mode="hour">Hour</button></div></div><canvas id="lossChart"></canvas></div>
</div>
<table><thead><tr><th>Host</th><th>Protocol</th><th>Status</th><th>RTT</th><th>Success Rate</th></tr></thead>
<tbody id="hosts"><tr><td colspan="5" style="text-align:center">Loading...</td></tr></tbody></table>
<div id="outages" style="display:none;margin-top:20px;background:rgba(255,82,82,0.05);border:1px solid rgba(255,82,82,0.2);border-radius:12px;padding:15px">
<h3 style="font-size:0.8rem;color:#ff5252;margin-bottom:10px">🚨 Recent Outages</h3>
<div id="outageList" style="font-size:0.85rem;color:#ccc"></div>
</div>
<div class="refresh">Auto-refreshes every 2s | Session: <span id="session">-</span></div>
</div>
<script>
const MAX_POINTS=60;
const liveData={rtt:{labels:[],data:[]},loss:{labels:[],data:[]}};
let minuteData={rtt:{},loss:{}},hourData={rtt:{},loss:{}};
let rttMode='live',lossMode='live';
const tooltipOpts={enabled:true,backgroundColor:'rgba(0,0,0,0.8)',titleColor:'#fff',bodyColor:'#fff',padding:10,displayColors:false,callbacks:{label:ctx=>ctx.dataset.label?ctx.dataset.label+': '+ctx.parsed.y.toFixed(2):ctx.parsed.y.toFixed(2)}};
const chartOpts={responsive:true,maintainAspectRatio:false,animation:{duration:300},interaction:{intersect:false,mode:'index'},scales:{x:{display:true,grid:{color:'rgba(255,255,255,0.05)'},ticks:{color:'#666',maxRotation:0,maxTicksLimit:8}},y:{grid:{color:'rgba(255,255,255,0.1)'},ticks:{color:'#888'}}},plugins:{legend:{display:false},tooltip:tooltipOpts}};
const rttChart=new Chart(document.getElementById('rttChart'),{type:'line',data:{labels:[],datasets:[{label:'RTT (ms)',data:[],borderColor:'#00d9ff',backgroundColor:'rgba(0,217,255,0.1)',fill:true,tension:0.3,pointRadius:2,pointHoverRadius:5}]},options:{...chartOpts,scales:{...chartOpts.scales,y:{...chartOpts.scales.y,min:0}}}});
const lossChart=new Chart(document.getElementById('lossChart'),{type:'bar',data:{labels:[],datasets:[{label:'Packet Loss (%)',data:[],backgroundColor:'rgba(255,82,82,0.7)',borderColor:'#ff5252',borderWidth:1}]},options:{...chartOpts,scales:{...chartOpts.scales,y:{...chartOpts.scales.y,min:0,suggestedMax:10}}}});
function updateChart(chart,labels,data){chart.data.labels=labels;chart.data.datasets[0].data=data;chart.update()}
function switchMode(chart,mode,btn){
document.querySelectorAll('[data-chart="'+chart+'"] .mode-btn').forEach(b=>b.classList.remove('active'));
btn.classList.add('active');
if(chart==='rtt')rttMode=mode;else lossMode=mode;
refreshCharts()}
function refreshCharts(){
if(rttMode==='live')updateChart(rttChart,liveData.rtt.labels.slice(),liveData.rtt.data.slice());
else if(rttMode==='minute'){let k=Object.keys(minuteData.rtt).sort().slice(-60);updateChart(rttChart,k.map(t=>t.slice(11,16)),k.map(t=>minuteData.rtt[t]))}
else{let k=Object.keys(hourData.rtt).sort().slice(-24);updateChart(rttChart,k.map(t=>t.slice(11,13)+':00'),k.map(t=>hourData.rtt[t]))}
if(lossMode==='live')updateChart(lossChart,liveData.loss.labels.slice(),liveData.loss.data.slice());
else if(lossMode==='minute'){let k=Object.keys(minuteData.loss).sort().slice(-60);updateChart(lossChart,k.map(t=>t.slice(11,16)),k.map(t=>minuteData.loss[t]))}
else{let k=Object.keys(hourData.loss).sort().slice(-24);updateChart(lossChart,k.map(t=>t.slice(11,13)+':00'),k.map(t=>hourData.loss[t]))}}
document.querySelectorAll('.mode-btn').forEach(btn=>btn.onclick=function(){switchMode(this.parentElement.dataset.chart,this.dataset.mode,this)});
function update(){fetch('/api/stats').then(r=>r.json()).then(d=>{
document.getElementById('sent').textContent=d.total_sent?.toLocaleString()||'-';
document.getElementById('recv').textContent=d.total_received?.toLocaleString()||'-';
let loss=d.packet_loss_percent||0;
document.getElementById('loss').textContent=loss.toFixed(2)+'%';
document.getElementById('loss').className='card-value '+(loss>30?'error':loss>5?'warning':'success');
let rtt=d.avg_rtt||0;
document.getElementById('rtt').textContent=rtt.toFixed(2)+' ms';
let s=document.getElementById('status');
s.textContent=loss>30?'● Outage':'● Online';s.className='status '+(loss>30?'status-error':'status-ok');
document.getElementById('hosts').innerHTML=(d.hosts||[]).map(h=>'<tr><td>'+h.name+'</td><td>'+h.protocol.toUpperCase()+'</td><td><span class="dot '+(h.online?'on':'off')+'"></span>'+(h.online?'Online':'Offline')+'</td><td>'+(h.rtt?h.rtt.toFixed(2)+' ms':'-')+'</td><td>'+h.success_rate.toFixed(1)+'%</td></tr>').join('')||'<tr><td colspan="5">No hosts</td></tr>';
document.getElementById('session').textContent=d.session_start||'-';
let outages=d.outages||[];
let outDiv=document.getElementById('outages');
if(outages.length>0){outDiv.style.display='block';document.getElementById('outageList').innerHTML=outages.slice(0,5).map(o=>'<div style="padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.05)"><strong>'+o.start+'</strong> → '+o.end+' <span style="color:#ff5252">('+o.duration+'s, '+o.loss_percent.toFixed(0)+'% loss)</span></div>').join('')}else{outDiv.style.display='none'}
let now=new Date().toLocaleTimeString();
liveData.rtt.labels.push(now);liveData.rtt.data.push(rtt);
liveData.loss.labels.push(now);liveData.loss.data.push(loss);
if(liveData.rtt.labels.length>MAX_POINTS){liveData.rtt.labels.shift();liveData.rtt.data.shift();liveData.loss.labels.shift();liveData.loss.data.shift()}
if(d.minute_data){minuteData.rtt=d.minute_data.rtt||{};minuteData.loss=d.minute_data.loss||{}}
if(d.hour_data){hourData.rtt=d.hour_data.rtt||{};hourData.loss=d.hour_data.loss||{}}
refreshCharts();
}).catch(e=>console.error(e))}
update();setInterval(update,2000);
</script></body></html>'''
    
    def __init__(self, port: int = 5000):
        self.port = port
        self.app = None
        
    def start(self, data_provider: Callable[[], Dict[str, Any]]):
        try:
            from flask import Flask, jsonify, Response
        except ImportError:
            print("⚠️ Flask not installed. Web dashboard disabled.")
            return False
        
        self.app = Flask(__name__)
        self.app.config['data_provider'] = data_provider
        template = self.HTML_TEMPLATE
        
        @self.app.route('/')
        def index():
            return Response(template, mimetype='text/html')
        
        @self.app.route('/api/stats')
        def stats():
            return jsonify(self.app.config['data_provider']())
        
        def run():
            import logging
            logging.getLogger('werkzeug').setLevel(logging.ERROR)
            self.app.run(host='0.0.0.0', port=self.port, threaded=True, use_reloader=False)
        
        threading.Thread(target=run, daemon=True).start()
        print(f"🌐 Web dashboard: http://localhost:{self.port}")
        
        import webbrowser
        webbrowser.open(f"http://localhost:{self.port}")
        return True


class NetworkMonitor:
    def __init__(self, config: argparse.Namespace):
        self.config = config
        self.hosts = self._parse_hosts(config.hosts)
        self.shutdown_requested = False
        self.host_data: Dict[str, Dict[str, Dict[str, AggregatedStats]]] = {}
        for host in self.hosts:
            self.host_data[host.name] = {'second': {}, 'minute': {}, 'hour': {}}
        self.last_results: Dict[str, TestResult] = {}
        self.startup_time = datetime.now()
        self.session_folder = f"session_{self.startup_time.strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.session_folder, exist_ok=True)
        self.alert_manager = AlertManager(self._get_alert_config())
        self.chart_generator = ChartGenerator(self.session_folder, silent=not config.generate_charts)
        self.web_dashboard: Optional[WebDashboard] = None
        if config.web_dashboard:
            self.web_dashboard = WebDashboard(config.web_port)
        self.last_write_time = time.time()
        self.last_cleanup_time = time.time()
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _parse_hosts(self, hosts_list: List[str]) -> List[HostConfig]:
        configs = []
        for host_str in hosts_list:
            parts = host_str.replace('/', ':').split(':')
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 53
            protocol = parts[2] if len(parts) > 2 else 'tcp'
            configs.append(HostConfig(host=host, port=port, protocol=protocol.lower()))
        return configs
    
    def _get_alert_config(self) -> Dict[str, Any]:
        config: Dict[str, Any] = {'webhooks': self.config.webhook_urls or [], 'cooldown': self.config.alert_cooldown}
        if self.config.email_to:
            config['email'] = {'enabled': True, 'from': self.config.email_from or self.config.email_user, 'to': self.config.email_to, 'smtp_host': self.config.smtp_host, 'smtp_port': self.config.smtp_port, 'username': self.config.email_user, 'password': self.config.email_pass}
        return config
    
    def _signal_handler(self, signum, frame):
        if not self.shutdown_requested:
            print("\n⏳ Shutting down...")
            self.shutdown_requested = True
        else:
            raise KeyboardInterrupt
    
    def _get_web_stats(self) -> Dict[str, Any]:
        total_sent = total_received = 0
        all_rtts: List[float] = []
        minute_rtt, minute_loss = {}, {}
        hour_rtt, hour_loss = {}, {}
        for data in self.host_data.values():
            for stats in data['second'].values():
                total_sent += stats.sent
                total_received += stats.received
                all_rtts.extend(stats.rtts)
            for key, stats in data['minute'].items():
                if key not in minute_rtt:
                    minute_rtt[key] = []
                    minute_loss[key] = []
                minute_rtt[key].append(stats.avg_rtt)
                minute_loss[key].append(stats.packet_loss * 100)
            for key, stats in data['hour'].items():
                if key not in hour_rtt:
                    hour_rtt[key] = []
                    hour_loss[key] = []
                hour_rtt[key].append(stats.avg_rtt)
                hour_loss[key].append(stats.packet_loss * 100)
        hosts_info = []
        for host in self.hosts:
            last_result = self.last_results.get(host.name)
            host_data = self.host_data[host.name]['second']
            total_success = sum(s.success_count for s in host_data.values())
            total_tests = sum(s.sent for s in host_data.values())
            hosts_info.append({
                'name': host.name, 'protocol': host.protocol,
                'online': last_result.success if last_result else False,
                'rtt': last_result.rtt_ms if last_result else None,
                'success_rate': (total_success / total_tests * 100) if total_tests > 0 else 0,
            })
        return {
            'total_sent': total_sent, 'total_received': total_received,
            'total_lost': total_sent - total_received,
            'packet_loss_percent': ((total_sent - total_received) / total_sent * 100) if total_sent > 0 else 0,
            'avg_rtt': sum(all_rtts) / len(all_rtts) if all_rtts else 0,
            'hosts': hosts_info, 'session_start': self.startup_time.strftime('%Y-%m-%d %H:%M:%S'),
            'outages': self._detect_outages(),
            'minute_data': {'rtt': {k: sum(v)/len(v) for k,v in minute_rtt.items()}, 'loss': {k: sum(v)/len(v) for k,v in minute_loss.items()}},
            'hour_data': {'rtt': {k: sum(v)/len(v) for k,v in hour_rtt.items()}, 'loss': {k: sum(v)/len(v) for k,v in hour_loss.items()}}
        }
    
    def _detect_outages(self) -> List[Dict[str, Any]]:
        all_outages: List[Dict[str, Any]] = []
        for host_name, data in self.host_data.items():
            second_data = data['second']
            bad_seconds = []
            for key in sorted(second_data.keys()):
                stats = second_data[key]
                if stats.sent > 0 and stats.packet_loss > self.config.packet_loss_threshold:
                    bad_seconds.append({'time': key, 'sent': stats.sent, 'received': stats.received, 'loss_percent': stats.packet_loss * 100})
            if not bad_seconds:
                continue
            current_outage: Optional[Dict[str, Any]] = None
            for sec in bad_seconds:
                sec_time = datetime.strptime(sec['time'], '%Y-%m-%d %H:%M:%S')
                if current_outage is None:
                    current_outage = {'host': host_name, 'start': sec['time'], 'end': sec['time'], 'sent': sec['sent'], 'received': sec['received'], 'seconds': [sec]}
                else:
                    last_time = datetime.strptime(current_outage['end'], '%Y-%m-%d %H:%M:%S')
                    if (sec_time - last_time).total_seconds() <= 1:
                        current_outage['end'] = sec['time']
                        current_outage['sent'] += sec['sent']
                        current_outage['received'] += sec['received']
                        current_outage['seconds'].append(sec)
                    else:
                        current_outage['duration'] = len(current_outage['seconds'])
                        current_outage['loss_percent'] = ((current_outage['sent'] - current_outage['received']) / current_outage['sent'] * 100) if current_outage['sent'] > 0 else 0
                        del current_outage['seconds']
                        all_outages.append(current_outage)
                        current_outage = {'host': host_name, 'start': sec['time'], 'end': sec['time'], 'sent': sec['sent'], 'received': sec['received'], 'seconds': [sec]}
            if current_outage:
                current_outage['duration'] = len(current_outage['seconds'])
                current_outage['loss_percent'] = ((current_outage['sent'] - current_outage['received']) / current_outage['sent'] * 100) if current_outage['sent'] > 0 else 0
                del current_outage['seconds']
                all_outages.append(current_outage)
        return sorted(all_outages, key=lambda x: x['start'], reverse=True)
    
    def _update_stats(self, host: HostConfig, result: TestResult):
        data = self.host_data[host.name]
        now = result.timestamp
        keys = [(now.strftime('%Y-%m-%d %H:%M:%S'), data['second']), (now.strftime('%Y-%m-%d %H:%M:00'), data['minute']), (now.strftime('%Y-%m-%d %H:00:00'), data['hour'])]
        for time_key, storage in keys:
            if time_key not in storage:
                storage[time_key] = AggregatedStats()
            stats = storage[time_key]
            stats.sent += 1
            if result.success:
                stats.received += 1
                stats.success_count += 1
                if result.rtt_ms is not None:
                    stats.rtts.append(result.rtt_ms)
            else:
                stats.fail_count += 1
    
    def _test_host(self, host: HostConfig) -> TestResult:
        if host.protocol == 'udp':
            return ConnectionTester.test_udp(host.host, host.port, self.config.timeout)
        return ConnectionTester.test_tcp(host.host, host.port, self.config.timeout)
    
    def _write_stats(self):
        for host in self.hosts:
            host_folder = os.path.join(self.session_folder, host.name.replace(':', '_').replace('/', '_'))
            os.makedirs(host_folder, exist_ok=True)
            data = self.host_data[host.name]
            DataExporter.to_txt(data['second'], os.path.join(host_folder, 'per_second.txt'), f"Per-second stats for {host.name}", "Time", self.config.packet_loss_threshold)
            DataExporter.to_txt(data['minute'], os.path.join(host_folder, 'per_minute.txt'), f"Per-minute stats for {host.name}", "Time", self.config.packet_loss_threshold)
            if self.config.export_csv:
                DataExporter.to_csv(data['second'], os.path.join(host_folder, 'data.csv'))
            if self.config.export_json:
                DataExporter.to_json(data['second'], os.path.join(host_folder, 'data.json'))
        outages = self._detect_outages()
        with open(os.path.join(self.session_folder, 'outages.txt'), 'w', encoding='utf-8') as f:
            if not outages:
                f.write("No outages detected.\n")
            else:
                f.write(f"Outages: {len(outages)}\n{'=' * 60}\n")
                for i, o in enumerate(outages, 1):
                    f.write(f"#{i} {o['host']}: {o['start']} - {o['end']} ({o['duration']}s, {o['loss_percent']:.1f}% loss)\n")
    
    def _cleanup_old_data(self):
        for data in self.host_data.values():
            sd = data['second']
            if len(sd) > self.config.max_seconds:
                for key in sorted(sd.keys())[:len(sd) - self.config.max_seconds]:
                    del sd[key]
    
    def _print_stats(self):
        total_sent = total_received = 0
        all_rtts: List[float] = []
        for data in self.host_data.values():
            keys = sorted(data['second'].keys())
            if len(keys) > 1:
                for key in keys[-int(self.config.write_interval)-1:-1]:
                    if key in data['second']:
                        s = data['second'][key]
                        total_sent += s.sent
                        total_received += s.received
                        all_rtts.extend(s.rtts)
        if total_sent == 0:
            return
        loss = (total_sent - total_received) / total_sent
        rtt = sum(all_rtts) / len(all_rtts) if all_rtts else 0
        now = datetime.now().strftime('%H:%M:%S')
        print(f"{now:<10} Sent:{total_sent:<8} Recv:{total_received:<8} RTT:{rtt:<8.2f}ms Loss:{loss*100:<6.1f}% {'⚠️ OUTAGE' if loss > self.config.packet_loss_threshold else '✓'}")
    
    def run(self):
        if self.web_dashboard:
            self.web_dashboard.start(self._get_web_stats)
        session_file = os.path.join(self.session_folder, 'session.txt')
        with open(session_file, 'w', encoding='utf-8') as f:
            f.write(f"Session: {self.startup_time.strftime('%Y-%m-%d %H:%M:%S')}\nHosts: {', '.join(h.name for h in self.hosts)}\n")
        print(f"🚀 Network Monitor Started")
        print(f"   Hosts: {', '.join(h.name for h in self.hosts)}")
        print(f"   Folder: {self.session_folder}/")
        print("-" * 80)
        try:
            while not self.shutdown_requested:
                for host in self.hosts:
                    result = self._test_host(host)
                    self.last_results[host.name] = result
                    self._update_stats(host, result)
                    if not result.success:
                        recent = self.host_data[host.name]['second']
                        keys = sorted(recent.keys())[-10:]
                        if keys:
                            rs = AggregatedStats()
                            for k in keys:
                                rs.sent += recent[k].sent
                                rs.received += recent[k].received
                            if rs.packet_loss > self.config.packet_loss_threshold:
                                self.alert_manager.alert_outage(host.name, rs.to_dict())
                ct = time.time()
                if ct - self.last_write_time >= self.config.write_interval:
                    self._write_stats()
                    self._print_stats()
                    self.last_write_time = ct
                if ct - self.last_cleanup_time >= 60:
                    self._cleanup_old_data()
                    self.last_cleanup_time = ct
                time.sleep(self.config.interval)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()
    
    def _shutdown(self):
        print("\n📊 Saving final stats...")
        self._write_stats()
        if self.config.generate_charts:
            for host in self.hosts:
                data = self.host_data[host.name]
                cg = ChartGenerator(os.path.join(self.session_folder, host.name.replace(':', '_').replace('/', '_')))
                cg.generate_all_charts(data['second'], data['minute'])
        total_sent = total_received = 0
        all_rtts: List[float] = []
        for data in self.host_data.values():
            for s in data['second'].values():
                total_sent += s.sent
                total_received += s.received
                all_rtts.extend(s.rtts)
        duration = datetime.now() - self.startup_time
        print(f"\n{'=' * 50}")
        print(f"Duration: {str(duration).split('.')[0]}")
        print(f"Sent: {total_sent:,} | Received: {total_received:,} | Lost: {total_sent - total_received:,}")
        print(f"Packet Loss: {((total_sent - total_received) / total_sent * 100) if total_sent > 0 else 0:.2f}%")
        print(f"Avg RTT: {sum(all_rtts) / len(all_rtts) if all_rtts else 0:.2f} ms")
        print(f"{'=' * 50}")
        print(f"📁 Saved to: {self.session_folder}/")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Network Connection Monitor', formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-H', '--hosts', nargs='+', default=DEFAULT_HOSTS, help='Hosts (host:port/protocol)')
    parser.add_argument('-i', '--interval', type=float, default=DEFAULT_INTERVAL, help='Test interval (seconds)')
    parser.add_argument('-t', '--timeout', type=float, default=DEFAULT_TIMEOUT, help='Timeout (seconds)')
    parser.add_argument('--threshold', type=float, default=DEFAULT_PACKET_LOSS_THRESHOLD, dest='packet_loss_threshold', help='Packet loss threshold')
    parser.add_argument('--write-interval', type=float, default=DEFAULT_FILE_WRITE_INTERVAL, dest='write_interval')
    parser.add_argument('--max-seconds', type=int, default=DEFAULT_MAX_SECONDS_IN_MEMORY, dest='max_seconds')
    parser.add_argument('--csv', action='store_true', dest='export_csv', help='Export CSV')
    parser.add_argument('--json', action='store_true', dest='export_json', help='Export JSON')
    parser.add_argument('--charts', action='store_true', dest='generate_charts', help='Generate charts')
    parser.add_argument('--web', action='store_true', dest='web_dashboard', help='Enable web dashboard')
    parser.add_argument('--web-port', type=int, default=5000, dest='web_port')
    parser.add_argument('--email-to', dest='email_to')
    parser.add_argument('--email-from', dest='email_from')
    parser.add_argument('--smtp-host', default='smtp.gmail.com', dest='smtp_host')
    parser.add_argument('--smtp-port', type=int, default=587, dest='smtp_port')
    parser.add_argument('--email-user', dest='email_user')
    parser.add_argument('--email-pass', dest='email_pass')
    parser.add_argument('--webhook', action='append', dest='webhook_urls')
    parser.add_argument('--alert-cooldown', type=int, default=300, dest='alert_cooldown')
    return parser.parse_args()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        sys.argv.extend(['--web'])
    config = parse_arguments()
    monitor = NetworkMonitor(config)
    monitor.run()
