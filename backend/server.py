import sys
import asyncio
import subprocess

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uvicorn
from monitor import DeviceMonitor

app = FastAPI(title="PerfHub Pro Backend")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import traceback

@app.get("/api/packages")
async def get_packages(os: str = "android", mock: str = "false"):
    is_mock = str(mock).lower() == "true"
    if is_mock:
        return {"packages": ["com.example.mock", "com.android.settings", "com.google.android.youtube"]}
        
    try:
        process = subprocess.Popen(
            "adb shell pm list packages",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        stdout, _ = await asyncio.to_thread(process.communicate)
        lines = stdout.decode('utf-8', errors='ignore').split('\n')
        
        packages = []
        for line in lines:
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line.replace("package:", ""))
        
        return {"packages": sorted(packages)}
    except Exception as e:
        print(f"Error fetching packages: {e}")
        return {"packages": []}

@app.websocket("/ws/perf")
async def websocket_endpoint(websocket: WebSocket, target: str = "", os: str = "android", mock: str = "false"):
    try:
        await websocket.accept()
    except (WebSocketDisconnect, RuntimeError):
        return
        
    is_mock = str(mock).lower() == "true"
    monitor = None
    device_info = {}
    
    try:
        while True:
            try:
                if not monitor:
                    monitor = DeviceMonitor(target=target, os_type=os, mock=is_mock)
                    device_info = monitor.get_device_info()
                    
                metrics = monitor.get_metrics()
                payload = {
                    "timestamp": datetime.now().astimezone().isoformat(),
                    "status_code": 200,
                    "device_info": device_info,
                    "metrics": metrics
                }
                await websocket.send_json(payload)
                await asyncio.sleep(0.5) # 2 Hz frequency
                
            except WebSocketDisconnect:
                print(f"Client disconnected for target: {target}")
                break
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
                await asyncio.sleep(0.5)
                
    except WebSocketDisconnect:
        print(f"Client disconnected for target: {target}")
    except Exception as e:
        print(f"WS Outer Error: {e}")

import json

@app.websocket("/ws/control")
async def websocket_control(websocket: WebSocket, target: str = "", mock: str = "false"):
    try:
        await websocket.accept()
    except (WebSocketDisconnect, RuntimeError):
        return
        
    is_mock = str(mock).lower() == "true"
    
    try:
        while True:
            try:
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
                    process = subprocess.Popen(cmd, shell=True)
                    await asyncio.to_thread(process.wait)
            except WebSocketDisconnect:
                print("Control client disconnected")
                break
            except Exception as e:
                print(f"Control inner error: {e}")
                await asyncio.sleep(0.5)
                
    except WebSocketDisconnect:
        print("Control client disconnected")
    except Exception as e:
        print(f"Control outer error: {e}")

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket, target: str = "", mock: str = "false"):
    try:
        await websocket.accept()
    except (WebSocketDisconnect, RuntimeError):
        return
        
    is_mock = str(mock).lower() == "true"
    if is_mock:
        return
        
    process = None
    try:
        try:
            monitor = DeviceMonitor(target=target, os_type="android", mock=is_mock)
        except Exception as e:
            print(f"Stream aborted during init: {e}")
            await websocket.close()
            return
            
        import shutil
        if not shutil.which("ffmpeg"):
            await websocket.send_text("[Stream Debug] ERROR: ffmpeg is not installed or not in PATH. Please restart the terminal if you just installed it.")
            await websocket.close()
            return
            
        # Scrcpy v2+ removed raw h264 record format. We must record to mkv and extract with ffmpeg.
        # Use scrcpy with ffmpeg via shell pipe.
        # CRITICAL: Kill any zombie scrcpy-server instances on the Android device!
        try:
            subprocess.run(["adb", "shell", "pkill", "app_process"], capture_output=True, timeout=2)
            await asyncio.sleep(0.5)
        except:
            pass

        # We must use gdigrab because --record=- causes Server connection failed on this specific Windows machine.
        # Force software rendering so gdigrab can capture it correctly!
        scrcpy_cmd = ["scrcpy", "-m", "1024", "-b", "1M", "--max-fps=30", "--render-driver=software", "--window-title", "PerfHub_Scrcpy", "--no-audio"]
        global scrcpy_proc
        scrcpy_proc = subprocess.Popen(scrcpy_cmd)
        
        # Wait for the scrcpy window to appear on the desktop
        await asyncio.sleep(2.0)
        
        # Capture the window using ffmpeg gdigrab and output raw H.264
        # Add -vf scale=512:1104 to force a fixed resolution! If the user resizes the window, the H264 decoder will crash if the resolution changes mid-stream.
        ffmpeg_cmd = ["ffmpeg", "-loglevel", "warning", "-f", "gdigrab", "-framerate", "30", "-i", "title=PerfHub_Scrcpy", "-vf", "scale=512:1104", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-f", "h264", "pipe:1"]
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        await asyncio.sleep(0.5)
            
        if process.poll() is not None:
            ffmpeg_err = await asyncio.to_thread(process.stderr.read)
            await websocket.send_text(f"[Stream Debug] ffmpeg gdigrab failed (code {process.returncode}): {ffmpeg_err.decode('utf-8', errors='ignore')}")
            await websocket.close()
            return
                
        # Background task to drain stderr and prevent pipe deadlock!
        async def drain_stderr(proc, name):
            try:
                while True:
                    line = await asyncio.to_thread(proc.stderr.readline)
                    if not line:
                        break
                    err_msg = line.decode('utf-8', errors='ignore').strip()
                    print(f"[{name} Err] {err_msg}")
                    try:
                        await websocket.send_text(f"[{name} Err] {err_msg}")
                    except:
                        pass
            except:
                pass
                
        asyncio.create_task(drain_stderr(process, "Stream"))
            
        while True:
            try:
                # Use read1 to avoid blocking until the buffer is completely full
                chunk = await asyncio.to_thread(process.stdout.read1, 65536)
                if not chunk:
                    break
                await websocket.send_bytes(chunk)
            except WebSocketDisconnect:
                print("Stream client disconnected")
                break
            except Exception as e:
                print(f"Stream inner error: {e}")
                await asyncio.sleep(1)
                
    except WebSocketDisconnect:
        print("Stream client disconnected")
    except Exception as e:
        print(f"Stream outer error: {e}")
    finally:
        # We must reference process if it was created
        if 'process' in locals() and process:
            try:
                process.terminate()
                process.wait()
            except:
                pass
        if 'scrcpy_proc' in locals() and scrcpy_proc:
            try:
                scrcpy_proc.terminate()
                scrcpy_proc.wait()
            except:
                pass

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, target: str = "", os: str = "android", mock: str = "false"):
    try:
        await websocket.accept()
    except (WebSocketDisconnect, RuntimeError):
        return
        
    is_mock = str(mock).lower() == "true"
    process = None
    import random
    
    try:
        monitor = None
        
        if is_mock:
            mock_errors = [
                "W/NetworkManager: Network connection slow or unstable",
                "E/AndroidRuntime: FATAL EXCEPTION: main"
            ]
            while True:
                try:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    error_msg = random.choice(mock_errors)
                    timestamp = datetime.now().strftime("%m-%d %H:%M:%S.%f")[:-3]
                    await websocket.send_text(f"{timestamp}  12345 12345 {error_msg}")
                except WebSocketDisconnect:
                    break
                except Exception:
                    await asyncio.sleep(1)
        else:
            while True:
                try:
                    if not monitor:
                        monitor = DeviceMonitor(target=target, os_type=os, mock=is_mock)
                    
                    if not target or target.lower() == "global":
                        cmd = "adb logcat -T 1 *:E"
                    else:
                        pid = monitor.get_pid()
                        if not pid:
                            await websocket.send_text("Error: Cannot find PID for target app")
                            await asyncio.sleep(2)
                            continue
                        cmd = f"adb logcat -T 1 --pid={pid} *:E"
                        
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    
                    while True:
                        line = await asyncio.to_thread(process.stdout.readline)
                        if not line:
                            # Process died or ended
                            err = await asyncio.to_thread(process.stderr.read)
                            if err:
                                await websocket.send_text(f"Logcat Error: {err.decode('utf-8', errors='ignore')}")
                            break
                        await websocket.send_text(line.decode('utf-8', errors='replace').strip())
                        
                    # If we broke out of the inner loop, it means process ended. Sleep before restarting to avoid tight loop.
                    await asyncio.sleep(2)
                    
                except WebSocketDisconnect:
                    print("Logs client disconnected")
                    break
                except Exception as e:
                    import traceback
                    error_str = str(e) or repr(e)
                    await websocket.send_text(f'{{"status_code": 500, "error_message": "{error_str}"}}')
                    await asyncio.sleep(2)
                    
    except WebSocketDisconnect:
        print("Logs client disconnected")
    except Exception as e:
        print(f"Logs error: {e}")
    finally:
        if process:
            try:
                process.terminate()
                process.wait()
            except:
                pass

if __name__ == "__main__":
    # Allow running directly via python server.py
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
