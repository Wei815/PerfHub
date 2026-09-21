import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uvicorn
from monitor import DeviceMonitor

app = FastAPI(title="PerfHub Pro Backend")

import traceback

@app.websocket("/ws/perf")
async def websocket_endpoint(websocket: WebSocket, target: str = "com.example.app", os: str = "android", mock: str = "false"):
    await websocket.accept()
    is_mock = str(mock).lower() == "true"
    monitor = DeviceMonitor(target=target, os_type=os, mock=is_mock)
    device_info = monitor.get_device_info()
    
    try:
        while True:
            try:
                metrics = monitor.get_metrics()
                payload = {
                    "timestamp": datetime.now().astimezone().isoformat(),
                    "status_code": 200,
                    "device_info": device_info,
                    "metrics": metrics
                }
            except Exception as e:
                print(f"WS Error: {traceback.format_exc()}")
                payload = {
                    "timestamp": datetime.now().astimezone().isoformat(),
                    "status_code": 500,
                    "error_message": str(e),
                    "metrics": {
                        "cpu_percent": 0,
                        "memory_mb": 0,
                        "fps": 0,
                        "rx_kbps": 0,
                        "tx_kbps": 0
                    }
                }
            
            await websocket.send_json(payload)
            await asyncio.sleep(1) # 1 Hz frequency
            
    except WebSocketDisconnect:
        print(f"Client disconnected for target: {target}")

import json

@app.websocket("/ws/control")
async def websocket_control(websocket: WebSocket, target: str = "com.example.app", mock: str = "false"):
    await websocket.accept()
    is_mock = str(mock).lower() == "true"
    try:
        while True:
            data = await websocket.receive_text()
            if is_mock:
                continue
            payload = json.loads(data)
            action = payload.get("action")
            cmd = None
            if action == "tap":
                cmd = f"adb shell input tap {payload['x']} {payload['y']}"
            elif action == "swipe":
                cmd = f"adb shell input swipe {payload['start_x']} {payload['start_y']} {payload['end_x']} {payload['end_y']} {payload.get('duration', 300)}"
            elif action == "keyevent":
                cmd = f"adb shell input keyevent {payload['keycode']}"
            
            if cmd:
                process = await asyncio.create_subprocess_shell(cmd)
                await process.communicate()
    except WebSocketDisconnect:
        print("Control client disconnected")
    except Exception as e:
        print(f"Control error: {e}")

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket, target: str = "com.example.app", mock: str = "false"):
    await websocket.accept()
    is_mock = str(mock).lower() == "true"
    if is_mock:
        return
        
    try:
        monitor = DeviceMonitor(target=target, os_type="android", mock=is_mock)
    except Exception as e:
        await websocket.close()
        print(f"Stream aborted: {e}")
        return

    process = None
    try:
        cmd = "scrcpy --no-window --codec=h264 --max-fps=30 --bit-rate=2M --output-format=raw -"
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        while True:
            chunk = await process.stdout.read(16384)
            if not chunk:
                break
            await websocket.send_bytes(chunk)
            
    except WebSocketDisconnect:
        print("Stream client disconnected")
    except Exception as e:
        print(f"Stream error: {e}")
    finally:
        if process:
            try:
                process.terminate()
                await process.wait()
            except:
                pass

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, target: str = "com.example.app", os: str = "android", mock: str = "false"):
    await websocket.accept()
    is_mock = str(mock).lower() == "true"
    monitor = DeviceMonitor(target=target, os_type=os, mock=is_mock)
    process = None
    
    import random
    
    try:
        if is_mock:
            mock_errors = [
                "W/NetworkManager: Network connection slow or unstable",
                "E/AndroidRuntime: FATAL EXCEPTION: main",
                "E/AndroidRuntime: java.lang.OutOfMemoryError: Failed to allocate a 1024 byte allocation with 512 free bytes",
                "W/System: A resource was acquired at attached stack trace but never released",
                "E/ActivityThread: Failed to find provider info for com.example.app",
                "W/RenderThread: Missed vsync by 15ms"
            ]
            while True:
                await asyncio.sleep(random.uniform(2.0, 5.0))
                error_msg = random.choice(mock_errors)
                timestamp = datetime.now().strftime("%m-%d %H:%M:%S.%f")[:-3]
                await websocket.send_text(f"{timestamp}  12345 12345 {error_msg}")
        else:
            pid = monitor.get_pid()
            if not pid:
                await websocket.send_text("Error: Cannot find PID for target app")
                return
            
            cmd = f"adb logcat -T 1 --pid={pid} *:W"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                await websocket.send_text(line.decode('utf-8', errors='replace').strip())
                
    except WebSocketDisconnect:
        print("Logs client disconnected")
    except Exception as e:
        print(f"Logs error: {e}")
    finally:
        if process:
            try:
                process.terminate()
                await process.wait()
            except:
                pass

if __name__ == "__main__":
    # Allow running directly via python server.py
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
