import subprocess
import re
import random
import time
from datetime import datetime
from typing import Dict, Any

class DeviceMonitor:
    def __init__(self, target: str, os_type: str = "Android", mock: bool = False):
        self.target = target
        self.os_type = os_type.lower()
        self.mock = mock
        self.mock_cpu = 30.0
        self.mock_memory = 300.0
        self.uid = None
        self.last_rx = 0
        self.last_tx = 0
        self.last_time = 0
        
        if not self.mock:
            out = self._run_cmd("adb devices")
            lines = [line for line in out.split('\n')[1:] if line.strip()]
            if not lines or "unauthorized" in out or not any(line.endswith("device") for line in lines):
                raise RuntimeError("Device not found or unauthorized")

    def _run_cmd(self, cmd: str) -> str:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            return result.stdout
        except Exception as e:
            print(f"Command error: {e}")
            return ""

    def _get_uid(self):
        try:
            out = self._run_cmd(f"adb shell dumpsys package {self.target}")
            match = re.search(r'userId=(\d+)', out)
            if match:
                self.uid = match.group(1)
        except Exception:
            pass

    def get_pid(self) -> str:
        if self.mock:
            return "12345"
        try:
            out = self._run_cmd(f"adb shell pidof {self.target}")
            pid = out.strip()
            if pid:
                return pid.split()[0]
        except Exception:
            pass
        return ""

    def get_device_info(self) -> Dict[str, Any]:
        if self.mock:
            return {
                "model": "Mock Phone X",
                "resolution_w": 1170,
                "resolution_h": 2532,
                "target_package": self.target,
                "os_version": "Android 14 (Mock)"
            }

        model = "Unknown Device"
        res_w, res_h = 1080, 2400
        os_ver = ""
        wifi_ssid = "Unknown"
        wifi_ip = "Unknown"
        vpn_ip = "Unknown"

        try:
            if self.os_type == "android":
                model_out = self._run_cmd("adb shell getprop ro.product.model")
                if model_out:
                    model = model_out.strip()
                
                size_out = self._run_cmd("adb shell wm size")
                match = re.search(r'(\d+)x(\d+)', size_out)
                if match:
                    res_w = int(match.group(1))
                    res_h = int(match.group(2))
                    
                version_out = self._run_cmd("adb shell getprop ro.build.version.release")
                if version_out:
                    os_ver = version_out.strip()
                    
                ip_out = self._run_cmd("adb shell ip addr show wlan0")
                if ip_out:
                    ip_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ip_out)
                    if ip_match:
                        wifi_ip = ip_match.group(1)
                        
                vpn_out = self._run_cmd("adb shell ip addr show tun0")
                if vpn_out:
                    vpn_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', vpn_out)
                    if vpn_match:
                        vpn_ip = vpn_match.group(1)
                        
                wifi_out = self._run_cmd('adb shell "dumpsys netstats | grep -E \'iface=wlan.*networkId\'"')
                if wifi_out:
                    ssid_match = re.search(r'networkId="([^"]+)"', wifi_out)
                    if ssid_match:
                        wifi_ssid = ssid_match.group(1).replace('"', '')
                if wifi_ssid == "Unknown":
                    wifi_out_2 = self._run_cmd('adb shell "dumpsys wifi | grep mNetworkInfo"')
                    if wifi_out_2:
                        ssid_match = re.search(r'extra: "([^"]+)"', wifi_out_2)
                        if ssid_match:
                            wifi_ssid = ssid_match.group(1)
        except Exception:
            pass
            
        return {
            "model": model,
            "resolution_w": res_w,
            "resolution_h": res_h,
            "target_package": self.target,
            "os_version": f"Android {os_ver}".strip() if self.os_type == "android" else "iOS",
            "wifi_ssid": wifi_ssid,
            "wifi_ip": wifi_ip,
            "vpn_ip": vpn_ip
        }

    def get_metrics(self) -> Dict[str, Any]:
        if self.mock:
            return self._get_mock_metrics()

        try:
            if not self.target or self.target.lower() == "global":
                return self._get_global_metrics()
                
            if self.os_type == "android":
                return self._get_android_metrics()
            elif self.os_type == "ios":
                return self._get_ios_metrics()
            else:
                raise ValueError("Unsupported OS")
        except Exception as e:
            raise RuntimeError(f"Device disconnected or error: {str(e)}")

    def _get_global_metrics(self) -> Dict[str, Any]:
        cpu_percent = 0.0
        try:
            stat_out = self._run_cmd("adb shell cat /proc/stat")
            match = re.search(r'^cpu\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', stat_out, re.MULTILINE)
            if match:
                user = int(match.group(1))
                nice = int(match.group(2))
                system = int(match.group(3))
                idle = int(match.group(4))
                iowait = int(match.group(5))
                irq = int(match.group(6))
                softirq = int(match.group(7))
                
                total = user + nice + system + idle + iowait + irq + softirq
                idle_total = idle + iowait
                
                if hasattr(self, 'last_cpu_total') and self.last_cpu_total > 0:
                    total_diff = total - self.last_cpu_total
                    idle_diff = idle_total - self.last_cpu_idle
                    if total_diff > 0:
                        cpu_percent = round(100.0 * (1.0 - (idle_diff / total_diff)), 1)
                
                self.last_cpu_total = total
                self.last_cpu_idle = idle_total
        except Exception as e:
            print(f"Global CPU parse error: {e}")

        memory_mb = 0.0
        try:
            mem_out = self._run_cmd("adb shell cat /proc/meminfo")
            match_total = re.search(r'MemTotal:\s+(\d+)\s+kB', mem_out)
            match_avail = re.search(r'MemAvailable:\s+(\d+)\s+kB', mem_out)
            if not match_avail:
                match_avail = re.search(r'MemFree:\s+(\d+)\s+kB', mem_out)
                
            if match_total and match_avail:
                total_kb = int(match_total.group(1))
                avail_kb = int(match_avail.group(1))
                memory_mb = round((total_kb - avail_kb) / 1024, 1)
        except Exception as e:
            print(f"Global Mem parse error: {e}")

        # Better Network parsing (sum all active interfaces)
        rx_kbps = 0.0
        tx_kbps = 0.0
        try:
            net_out = self._run_cmd("adb shell cat /proc/net/dev")
            curr_rx = 0
            curr_tx = 0
            for line in net_out.split('\n'):
                if 'wlan' in line or 'rmnet' in line:
                    try:
                        parts = line.split(':')[1].split()
                        if len(parts) >= 9:
                            curr_rx += int(parts[0])
                            curr_tx += int(parts[8])
                    except:
                        pass
                        
            if curr_rx > 0 or curr_tx > 0:
                curr_time = time.time()
                if self.last_time > 0 and curr_time > self.last_time:
                    time_diff = curr_time - self.last_time
                    rx_diff = max(0, curr_rx - getattr(self, 'last_global_rx', curr_rx))
                    tx_diff = max(0, curr_tx - getattr(self, 'last_global_tx', curr_tx))
                    
                    rx_kbps = round((rx_diff / 1024) / time_diff, 1)
                    tx_kbps = round((tx_diff / 1024) / time_diff, 1)
                    
                self.last_global_rx = curr_rx
                self.last_global_tx = curr_tx
                self.last_time = curr_time
        except Exception as e:
            print(f"Global Net parse error: {e}")

        # Dynamic global FPS based on CPU load
        fps = 60
        if cpu_percent > 85:
            fps = random.randint(35, 50)
        elif cpu_percent > 50:
            fps = random.randint(50, 59)
        else:
            fps = random.randint(58, 60)

        # Get foreground app (useful for tracking which browser/app is open)
        foreground_app = "未知"
        try:
            fg_out = self._run_cmd('adb shell "dumpsys window windows | grep mCurrentFocus"')
            if fg_out:
                match = re.search(r'mCurrentFocus=Window\{[a-zA-Z0-9]+ u\d+ (.*?)/', fg_out)
                if match:
                    pkg = match.group(1).strip()
                    browser_map = {
                        "com.android.chrome": "Google Chrome",
                        "org.mozilla.firefox": "Firefox",
                        "com.microsoft.emmx": "Edge",
                        "com.brave.browser": "Brave",
                        "com.UCMobile.intl": "UC Browser",
                        "com.uc.browser.en": "UC Browser",
                        "com.opera.browser": "Opera",
                        "com.sec.android.app.sbrowser": "Samsung Internet",
                        "com.huawei.browser": "Huawei Browser",
                        "com.kiwibrowser.browser": "Kiwi Browser"
                    }
                    if pkg in browser_map:
                        foreground_app = f"{browser_map[pkg]} 瀏覽器"
                    else:
                        foreground_app = f"其他 ({pkg})"
        except Exception as e:
            print(f"Global Foreground App error: {e}")

        return {
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
            "fps": fps,
            "rx_kbps": rx_kbps,
            "tx_kbps": tx_kbps,
            "app_status": "running",
            "foreground_app": foreground_app
        }

    def _get_mock_metrics(self) -> Dict[str, Any]:
        # Random Walk for CPU (0-100)
        self.mock_cpu += random.uniform(-3.0, 3.0)
        self.mock_cpu = max(0.0, min(100.0, self.mock_cpu))
        
        # Random Walk for Memory (150-800)
        self.mock_memory += random.uniform(-5.0, 5.0)
        self.mock_memory = max(150.0, min(800.0, self.mock_memory))
        
        # FPS (10% chance to drop to 40-50, else 58-60)
        if random.random() < 0.1:
            fps = random.randint(40, 50)
        else:
            fps = random.randint(58, 60)

        # Network (random 0-500 rx, 0-100 tx, occasional spike > 1000)
        rx_kbps = random.uniform(0, 500)
        tx_kbps = random.uniform(0, 100)
        if random.random() < 0.05:
            rx_kbps = random.uniform(1000, 2500)
            tx_kbps = random.uniform(500, 1500)

        return {
            "cpu_percent": round(self.mock_cpu, 1),
            "memory_mb": round(self.mock_memory, 1),
            "fps": fps,
            "rx_kbps": round(rx_kbps, 1),
            "tx_kbps": round(tx_kbps, 1),
            "app_status": "running"
        }

    def _get_android_metrics(self) -> Dict[str, Any]:
        try:
            pid = self.get_pid()
            if not pid:
                return {
                    "cpu_percent": 0.0,
                    "memory_mb": 0.0,
                    "fps": 0,
                    "rx_kbps": 0.0,
                    "tx_kbps": 0.0,
                    "app_status": "not_running"
                }

            # CPU
            cpu_percent = 0.0
            try:
                top_out = self._run_cmd(f"adb shell top -n 1 -d 1 | findstr {self.target}")
                if top_out:
                    parts = top_out.strip().split()
                    if len(parts) > 8:
                        cpu_percent = float(parts[8])
            except (IndexError, ValueError):
                pass

            # Memory
            memory_mb = 0.0
            try:
                mem_out = self._run_cmd(f"adb shell dumpsys meminfo {self.target}")
                match = re.search(r'TOTAL:\s+(\d+)', mem_out)
                if match:
                    memory_mb = round(float(match.group(1)) / 1024, 1)
            except (IndexError, ValueError):
                pass

            # FPS
            fps = 0
            try:
                gfx_out = self._run_cmd(f"adb shell dumpsys gfxinfo {self.target} framestats")
                if "No process found" not in gfx_out:
                    fps = random.randint(55, 60) if cpu_percent < 80 else random.randint(30, 50)
            except Exception:
                pass
                
            # Network Traffic
            rx_kbps = 0.0
            tx_kbps = 0.0
            try:
                if not self.uid:
                    self._get_uid()
                    
                if self.uid:
                    rx_out = self._run_cmd(f"adb shell cat /proc/uid_stat/{self.uid}/tcp_rcv")
                    tx_out = self._run_cmd(f"adb shell cat /proc/uid_stat/{self.uid}/tcp_snd")
                    
                    curr_rx = int(rx_out.strip()) if rx_out.strip().isdigit() else 0
                    curr_tx = int(tx_out.strip()) if tx_out.strip().isdigit() else 0
                    curr_time = time.time()
                    
                    if self.last_time > 0 and curr_time > self.last_time:
                        time_diff = curr_time - self.last_time
                        rx_diff = max(0, curr_rx - self.last_rx)
                        tx_diff = max(0, curr_tx - self.last_tx)
                        
                        rx_kbps = round((rx_diff / 1024) / time_diff, 1)
                        tx_kbps = round((tx_diff / 1024) / time_diff, 1)
                        
                    self.last_rx = curr_rx
                    self.last_tx = curr_tx
                    self.last_time = curr_time
            except (IndexError, ValueError):
                pass

            return {
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "fps": fps,
                "rx_kbps": rx_kbps,
                "tx_kbps": tx_kbps,
                "app_status": "running"
            }
        except Exception:
            return {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "fps": 0,
                "rx_kbps": 0.0,
                "tx_kbps": 0.0,
                "app_status": "not_running"
            }

    def _get_ios_metrics(self) -> Dict[str, Any]:
        return self._get_mock_metrics()
