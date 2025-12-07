import socket
import time
from datetime import datetime
import os
import signal

# ============== CONFIGURATION ==============
host = '1.1.1.1'  # Cloudflare DNS
port = 53  # DNS port
interval = 0.001  # 1ms interval - max frequency
timeout = 0.025   # 25ms timeout
PACKET_LOSS_THRESHOLD = 0.3  # 30% packet loss = outage

# Save to connection_log.txt (True/False)
SAVE_CONNECTION_LOG = False  # Disabled for speed

# How often to write to files and print to console (seconds)
FILE_WRITE_INTERVAL = 10  # Write and print every 10 seconds

# RAM Management - keep data for last N seconds (older data is purged)
MAX_SECONDS_IN_MEMORY = 3600  # Keep 1 hour of second-by-second data
# ==========================================

# Graceful shutdown flag
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle Ctrl+C signal for graceful shutdown"""
    global shutdown_requested
    if not shutdown_requested:
        print("\n⏳ Shutting down... (waiting for current cycle to complete)")
        shutdown_requested = True
    else:
        print("\n⚠️ Forced shutdown!")
        raise KeyboardInterrupt

signal.signal(signal.SIGINT, signal_handler)

def test_connection(host, port, timeout):
    """Test TCP connection to host:port and return success status and RTT"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.time()
        sock.connect((host, port))
        end = time.time()
        sock.close()
        return True, (end - start) * 1000  # RTT in ms
    except Exception:
        return False, None

def write_stats_to_file(filepath, title, time_key_name, data_dict):
    """Write statistics to file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"{title}:\n")
        f.write("=" * 100 + "\n")
        f.write(f"{time_key_name:<20} {'Sent':<12} {'Received':<12} {'Avg RTT (ms)':<18} {'Success':<12} {'Failed':<12} {'Outage':<10}\n")
        f.write("-" * 100 + "\n")
        
        for key in sorted(data_dict.keys()):
            data = data_dict[key]
            avg_rtt = sum(data['rtts']) / len(data['rtts']) if data['rtts'] else 0
            # Outage = any failure OR packet loss > threshold
            packet_loss = (data['sent'] - data['received']) / data['sent'] if data['sent'] > 0 else 0
            outage = packet_loss > PACKET_LOSS_THRESHOLD
            
            f.write(f"{key:<20} {data['sent']:<12} {data['received']:<12} {avg_rtt:<18.2f} "
                   f"{data['success_count']:<12} {data['fail_count']:<12} {'Yes' if outage else 'No':<10}\n")

def write_packet_loss_to_file(filepath, packet_loss_outages):
    """Write packet loss to packetloss.txt - merges consecutive outages"""
    with open(filepath, 'w', encoding='utf-8') as f:
        if not packet_loss_outages:
            f.write("No packet loss was detected.\n")
            return
        
        f.write(f"Packet loss outages - {len(packet_loss_outages)} outages\n")
        f.write("=" * 100 + "\n\n")
        
        for i, outage in enumerate(packet_loss_outages, 1):
            duration = outage['duration']
            f.write(f"Outage #{i}:\n")
            f.write(f"  From: {outage['start']}\n")
            f.write(f"  To: {outage['end']}\n")
            f.write(f"  Duration: {duration} second{'s' if duration != 1 else ''}\n")
            f.write(f"  Sent: {outage['sent']} | Received: {outage['received']} | Loss: {outage['loss_percent']:.1f}%\n")
            f.write("-" * 100 + "\n")

def detect_packet_loss_outages(second_data):
    """Detect outages based on packet loss - merges consecutive seconds"""
    # Find all seconds with packet loss
    bad_seconds = []
    for key in sorted(second_data.keys()):
        data = second_data[key]
        if data['sent'] > 0:
            packet_loss = (data['sent'] - data['received']) / data['sent']
            if packet_loss > PACKET_LOSS_THRESHOLD:
                bad_seconds.append({
                    'time': key,
                    'sent': data['sent'],
                    'received': data['received'],
                    'loss_percent': packet_loss * 100
                })
    
    if not bad_seconds:
        return []
    
    # Merge consecutive seconds into outages
    outages = []
    current_outage = None
    
    for sec in bad_seconds:
        sec_time = datetime.strptime(sec['time'], '%Y-%m-%d %H:%M:%S')
        
        if current_outage is None:
            # Start new outage
            current_outage = {
                'start': sec['time'],
                'end': sec['time'],
                'sent': sec['sent'],
                'received': sec['received'],
                'seconds': [sec]
            }
        else:
            # Check if this is a consecutive second
            last_time = datetime.strptime(current_outage['end'], '%Y-%m-%d %H:%M:%S')
            if (sec_time - last_time).total_seconds() <= 1:
                # Consecutive second - add to current outage
                current_outage['end'] = sec['time']
                current_outage['sent'] += sec['sent']
                current_outage['received'] += sec['received']
                current_outage['seconds'].append(sec)
            else:
                # New outage - save previous and start new
                current_outage['duration'] = len(current_outage['seconds'])
                current_outage['loss_percent'] = ((current_outage['sent'] - current_outage['received']) / current_outage['sent'] * 100) if current_outage['sent'] > 0 else 0
                del current_outage['seconds']
                outages.append(current_outage)
                
                current_outage = {
                    'start': sec['time'],
                    'end': sec['time'],
                    'sent': sec['sent'],
                    'received': sec['received'],
                    'seconds': [sec]
                }
    
    # Don't forget the last outage
    if current_outage:
        current_outage['duration'] = len(current_outage['seconds'])
        current_outage['loss_percent'] = ((current_outage['sent'] - current_outage['received']) / current_outage['sent'] * 100) if current_outage['sent'] > 0 else 0
        del current_outage['seconds']
        outages.append(current_outage)
    
    return outages

def cleanup_old_data(second_data, max_entries):
    """Remove old entries from second_data to manage RAM usage"""
    if len(second_data) > max_entries:
        sorted_keys = sorted(second_data.keys())
        keys_to_remove = sorted_keys[:len(sorted_keys) - max_entries]
        for key in keys_to_remove:
            del second_data[key]
        return len(keys_to_remove)
    return 0

# Create folder with date and time at startup
startup_time = datetime.now()
session_folder = f"session_{startup_time.strftime('%Y%m%d_%H%M%S')}"
os.makedirs(session_folder, exist_ok=True)

# File paths
session_file_path = os.path.join(session_folder, f"session_{startup_time.strftime('%Y%m%d_%H%M%S')}.txt")
log_file_path = os.path.join(session_folder, 'connection_log.txt')
second_avg_path = os.path.join(session_folder, 'averages_per_second.txt')
minute_avg_path = os.path.join(session_folder, 'averages_per_minute.txt')
hour_avg_path = os.path.join(session_folder, 'averages_per_hour.txt')
packet_loss_path = os.path.join(session_folder, 'packetloss.txt')

# Create session file
with open(session_file_path, 'w', encoding='utf-8') as session_file:
    session_file.write(f"Session started: {startup_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
    session_file.write(f"Host: {host}\n")
    session_file.write(f"Port: {port}\n")
    session_file.write(f"Interval: {interval} seconds\n")
    session_file.write(f"Connection log: {'Enabled' if SAVE_CONNECTION_LOG else 'Disabled'}\n")
    session_file.write(f"Packet loss threshold: {PACKET_LOSS_THRESHOLD * 100}%\n")
    session_file.write(f"Max seconds in memory: {MAX_SECONDS_IN_MEMORY}\n")
    session_file.write("=" * 80 + "\n\n")

print(f"Monitoring started. Press Ctrl+C to stop.")
print(f"Packet loss threshold: {PACKET_LOSS_THRESHOLD * 100:.0f}%")
print(f"Session folder: {session_folder}")
print(f"Statistics update every {FILE_WRITE_INTERVAL} seconds.")
print(f"RAM management: keeping last {MAX_SECONDS_IN_MEMORY} seconds in memory.")
print("-" * 120)
print(f"{'Time range (10s)':<28} {'Sent':<12} {'Received':<12} {'Avg RTT (ms)':<18} {'Success':<12} {'Failed':<12} {'Outage':<10}")
print("-" * 120)

# Data in memory
second_data = {}
minute_data = {}
hour_data = {}

last_process_time = time.time()
last_cleanup_time = time.time()

# Open log file only if enabled
log_file = None
if SAVE_CONNECTION_LOG:
    log_file = open(log_file_path, 'a', encoding='utf-8')

try:
    while not shutdown_requested:
        now = datetime.now()
        timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        success, rtt = test_connection(host, port, timeout)
        packets_sent = 1
        packets_received = 1 if success else 0
        
        # Write to connection_log.txt if enabled
        if SAVE_CONNECTION_LOG and log_file:
            rtt_str = f"{rtt:.2f} ms" if rtt else "N/A"
            log_line = f"{timestamp_str} - Sent: {packets_sent}, Received: {packets_received}, RTT: {rtt_str}, Success: {success}\n"
            log_file.write(log_line)
            log_file.flush()
        
        # Keys for aggregation
        second_key = now.strftime('%Y-%m-%d %H:%M:%S')
        minute_key = now.strftime('%Y-%m-%d %H:%M:00')
        hour_key = now.strftime('%Y-%m-%d %H:00:00')
        
        # Update per-second data
        if second_key not in second_data:
            second_data[second_key] = {'sent': 0, 'received': 0, 'rtts': [], 'success_count': 0, 'fail_count': 0}
        second_data[second_key]['sent'] += packets_sent
        second_data[second_key]['received'] += packets_received
        if rtt is not None:
            second_data[second_key]['rtts'].append(rtt)
        if success:
            second_data[second_key]['success_count'] += 1
        else:
            second_data[second_key]['fail_count'] += 1
        
        # Update per-minute data
        if minute_key not in minute_data:
            minute_data[minute_key] = {'sent': 0, 'received': 0, 'rtts': [], 'success_count': 0, 'fail_count': 0}
        minute_data[minute_key]['sent'] += packets_sent
        minute_data[minute_key]['received'] += packets_received
        if rtt is not None:
            minute_data[minute_key]['rtts'].append(rtt)
        if success:
            minute_data[minute_key]['success_count'] += 1
        else:
            minute_data[minute_key]['fail_count'] += 1
        
        # Update per-hour data
        if hour_key not in hour_data:
            hour_data[hour_key] = {'sent': 0, 'received': 0, 'rtts': [], 'success_count': 0, 'fail_count': 0}
        hour_data[hour_key]['sent'] += packets_sent
        hour_data[hour_key]['received'] += packets_received
        if rtt is not None:
            hour_data[hour_key]['rtts'].append(rtt)
        if success:
            hour_data[hour_key]['success_count'] += 1
        else:
            hour_data[hour_key]['fail_count'] += 1
        
        # Write statistics and print to console at interval
        current_time = time.time()
        if current_time - last_process_time >= FILE_WRITE_INTERVAL:
            # Detect packet loss outages
            packet_loss_outages = detect_packet_loss_outages(second_data)
            
            # Write to files
            write_stats_to_file(second_avg_path, "Per-second totals", "Time", second_data)
            write_stats_to_file(minute_avg_path, "Per-minute totals", "Time (minute)", minute_data)
            write_stats_to_file(hour_avg_path, "Per-hour totals", "Time (hour)", hour_data)
            write_packet_loss_to_file(packet_loss_path, packet_loss_outages)
            
            # Print to console - sum of last 10 seconds
            sorted_keys = sorted(second_data.keys())
            if len(sorted_keys) >= 2:
                # Take last 10 complete seconds (excluding current)
                last_10_keys = sorted_keys[-11:-1] if len(sorted_keys) > 11 else sorted_keys[:-1]
                
                if last_10_keys:
                    # Totals for last 10 seconds
                    total_sent = sum(second_data[k]['sent'] for k in last_10_keys)
                    total_received = sum(second_data[k]['received'] for k in last_10_keys)
                    all_rtts = [rtt for k in last_10_keys for rtt in second_data[k]['rtts']]
                    avg_rtt = sum(all_rtts) / len(all_rtts) if all_rtts else 0
                    total_success = sum(second_data[k]['success_count'] for k in last_10_keys)
                    total_fail = sum(second_data[k]['fail_count'] for k in last_10_keys)
                    
                    packet_loss = (total_sent - total_received) / total_sent if total_sent > 0 else 0
                    outage = packet_loss > PACKET_LOSS_THRESHOLD
                    outage_text = "Yes" if outage else "No"
                    
                    # Time range
                    time_range = f"{last_10_keys[0]} - {last_10_keys[-1][-8:]}"
                    
                    print(f"{time_range:<28} {total_sent:<12} {total_received:<12} {avg_rtt:<18.2f} "
                          f"{total_success:<12} {total_fail:<12} {outage_text:<10}")
            
            last_process_time = current_time
        
        # RAM cleanup - remove old second data periodically (every 60 seconds)
        if current_time - last_cleanup_time >= 60:
            removed = cleanup_old_data(second_data, MAX_SECONDS_IN_MEMORY)
            if removed > 0:
                pass  # Silently clean up old data
            last_cleanup_time = current_time
        
        time.sleep(interval)

except KeyboardInterrupt:
    # Forced shutdown (second Ctrl+C)
    print("\n⚠️ Forced interrupt!")

finally:
    # Cleanup is ALWAYS performed (normal and forced shutdown)
    end_time = datetime.now()
    print("\n\nMonitoring stopped.")
    if log_file:
        log_file.close()
    
    # Calculate total statistics
    total_sent = sum(d['sent'] for d in second_data.values())
    total_received = sum(d['received'] for d in second_data.values())
    total_lost = total_sent - total_received
    loss_percent = (total_lost / total_sent * 100) if total_sent > 0 else 0
    duration = end_time - startup_time
    duration_str = str(duration).split('.')[0]  # Without microseconds
    
    all_rtts = [rtt for d in second_data.values() for rtt in d['rtts']]
    avg_rtt = sum(all_rtts) / len(all_rtts) if all_rtts else 0
    
    # Final statistics write
    packet_loss_outages = detect_packet_loss_outages(second_data)
    write_stats_to_file(second_avg_path, "Per-second totals", "Time", second_data)
    write_stats_to_file(minute_avg_path, "Per-minute totals", "Time (minute)", minute_data)
    write_stats_to_file(hour_avg_path, "Per-hour totals", "Time (hour)", hour_data)
    write_packet_loss_to_file(packet_loss_path, packet_loss_outages)
    
    # Add final statistics to session file
    with open(session_file_path, 'a', encoding='utf-8') as session_file:
        session_file.write(f"\n{'=' * 80}\n")
        session_file.write(f"Session ended: {end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
        session_file.write(f"{'=' * 80}\n\n")
        session_file.write(f"TOTAL STATISTICS:\n")
        session_file.write(f"-" * 40 + "\n")
        session_file.write(f"Duration:         {duration_str}\n")
        session_file.write(f"Sent:             {total_sent} packets\n")
        session_file.write(f"Received:         {total_received} packets\n")
        session_file.write(f"Lost:             {total_lost} packets ({loss_percent:.2f}%)\n")
        session_file.write(f"Average RTT:      {avg_rtt:.2f} ms\n")
        session_file.write(f"Packet loss outages: {len(packet_loss_outages)}\n")
    
    print(f"\n{'=' * 60}")
    print(f"TOTAL STATISTICS:")
    print(f"  Duration:      {duration_str}")
    print(f"  Sent:          {total_sent} packets")
    print(f"  Received:      {total_received} packets")
    print(f"  Lost:          {total_lost} packets ({loss_percent:.2f}%)")
    print(f"  Average RTT:   {avg_rtt:.2f} ms")
    print(f"{'=' * 60}")
    print(f"Statistics saved to: {session_folder}/")
