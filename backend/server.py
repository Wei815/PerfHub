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
    
    phys_w, phys_h = 1080, 2400
    is_landscape = False
    if not is_mock:
        try:
            wm_size_out = await asyncio.to_thread(subprocess.check_output, ["adb", "shell", "wm", "size"], text=True, timeout=2)
            if "Physical size:" in wm_size_out:
                parts = wm_size_out.split(":")[1].strip().split("x")
                phys_w, phys_h = int(parts[0]), int(parts[1])
        except:
            pass
            
        try:
            adb_out = await asyncio.to_thread(subprocess.check_output, ["adb", "shell", "dumpsys", "input"], text=True, timeout=3)
            for line in adb_out.splitlines():
                if "SurfaceOrientation" in line:
                    val = line.split(":")[1].strip()
                    if val in ["1", "3"]:
                        is_landscape = True
                    break
        except:
            pass
            
    if is_landscape:
        phys_w, phys_h = max(phys_w, phys_h), min(phys_w, phys_h)
    else:
        phys_w, phys_h = min(phys_w, phys_h), max(phys_w, phys_h)
    
    import ctypes
    from ctypes import wintypes
    
    # State for fallback swipe/tap detection
    fallback_state = {}
    
    cached_hwnd = 0
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
                if is_mock:
                    continue
                payload = json.loads(data)
                action = payload.get("action")
                
                # Check if cached hwnd is still valid
                if cached_hwnd != 0 and not ctypes.windll.user32.IsWindow(cached_hwnd):
                    cached_hwnd = 0
                
                if cached_hwnd == 0:
                    def enum_cb(h, _):
                        nonlocal cached_hwnd
                        import ctypes
                        length = ctypes.windll.user32.GetWindowTextLengthW(h)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            ctypes.windll.user32.GetWindowTextW(h, buff, length + 1)
                            title = buff.value
                            if "PerfHub_Scrcpy" in title and "Visual Studio" not in title and "Code" not in title and "Command Prompt" not in title and "PowerShell" not in title:
                                cached_hwnd = h
                                return False # Stop enumerating
                        return True
                    
                    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
                    enum_func = CMPFUNC(enum_cb)
                    ctypes.windll.user32.EnumWindows(enum_func, 0)
                
                injected = False
                debug_info = ""
                
                if cached_hwnd != 0:
                    rect = wintypes.RECT()
                    ctypes.windll.user32.GetClientRect(cached_hwnd, ctypes.byref(rect))
                    cw = rect.right - rect.left
                    ch = rect.bottom - rect.top
                    if cw > 0 and ch > 0:
                        cx = int(payload.get('relX', 0) * cw)
                        cy = int(payload.get('relY', 0) * ch)
                        lparam = (cy << 16) | cx
                        
                        # Fake focus to ensure SDL2 accepts background input
                        ctypes.windll.user32.SendMessageW(cached_hwnd, 0x0006, 1, 0) # WM_ACTIVATE WA_ACTIVE
                        ctypes.windll.user32.SendMessageW(cached_hwnd, 0x0007, 0, 0) # WM_SETFOCUS
                        if action == "down":
                            has_moved = False
                            rel_x = payload.get('relX', 0)
                            rel_y = payload.get('relY', 0)
                            debug_info = f"Backend (Down): relX={rel_x:.3f}, relY={rel_y:.3f} | cx={cx}, cy={cy} (Window: {cw}x{ch})"
                            ctypes.windll.user32.PostMessageW(cached_hwnd, 0x0200, 0, lparam) # Move mouse (not pressed)
                            ctypes.windll.user32.PostMessageW(cached_hwnd, 0x0201, 1, lparam) # WM_LBUTTONDOWN
                            injected = True
                        elif action == "move":
                            has_moved = True
                            rel_x = payload.get('relX', 0)
                            rel_y = payload.get('relY', 0)
                            debug_info = f"Backend (Move): relX={rel_x:.3f}, relY={rel_y:.3f} | cx={cx}, cy={cy}"
                            ctypes.windll.user32.PostMessageW(cached_hwnd, 0x0200, 1, lparam) # Move mouse (pressed)
                            injected = True
                        elif action == "hover":
                            ctypes.windll.user32.PostMessageW(cached_hwnd, 0x0200, 0, lparam) # Move mouse (not pressed)
                            injected = True
                        elif action == "up":
                            if not has_moved:
                                await asyncio.sleep(0.15) # 150ms delay to ensure the tap registers on slow Android devices (pure tap only)
                            ctypes.windll.user32.PostMessageW(cached_hwnd, 0x0202, 0, lparam) # WM_LBUTTONUP
                            injected = True
                
                # If PostMessageW failed (e.g. window not found), fallback to ADB (slow but reliable)
                if not injected:
                    if action == "down":
                        ax = int(payload.get('realX', payload.get('relX', 0) * phys_w))
                        ay = int(payload.get('realY', payload.get('relY', 0) * phys_h))
                        debug_info = f"Backend (ADB Fallback): => ax={ax}, ay={ay} (Screen: {phys_w}x{phys_h})"
                        fallback_state['x'] = ax
                        fallback_state['y'] = ay
                        fallback_state['time'] = asyncio.get_event_loop().time()
                    elif action == "up":
                        if 'x' in fallback_state:
                            end_x = payload.get('realX', payload.get('relX', 0) * phys_w)
                            end_y = payload.get('realY', payload.get('relY', 0) * phys_h)
                            duration = (asyncio.get_event_loop().time() - fallback_state['time']) * 1000
                            dist = ((end_x - fallback_state['x'])**2 + (end_y - fallback_state['y'])**2)**0.5
                            
                            if dist < 20 and duration < 300:
                                subprocess.Popen(["adb", "shell", "input", "tap", str(int(end_x)), str(int(end_y))], creationflags=subprocess.CREATE_NO_WINDOW)
                            else:
                                subprocess.Popen(["adb", "shell", "input", "swipe", str(int(fallback_state['x'])), str(int(fallback_state['y'])), str(int(end_x)), str(int(end_y)), str(min(int(duration), 2000))], creationflags=subprocess.CREATE_NO_WINDOW)
                            fallback_state.clear()
                    elif action == "tap":
                        subprocess.Popen(["adb", "shell", "input", "tap", str(payload['x']), str(payload['y'])], creationflags=subprocess.CREATE_NO_WINDOW)
                    elif action == "swipe":
                        subprocess.Popen(["adb", "shell", "input", "swipe", str(payload['start_x']), str(payload['start_y']), str(payload['end_x']), str(payload['end_y']), str(payload.get('duration', 300))], creationflags=subprocess.CREATE_NO_WINDOW)
                elif action == "keyevent":
                    subprocess.Popen(["adb", "shell", "input", "keyevent", str(payload['keycode'])], creationflags=subprocess.CREATE_NO_WINDOW)
                    
                if action == "down" and debug_info:
                    try:
                        await websocket.send_json({"type": "debug_click", "info": debug_info})
                    except Exception as e:
                        pass
                elif action == "move" and debug_info:
                    try:
                        await websocket.send_json({"type": "debug_move", "info": debug_info})
                    except Exception as e:
                        pass
                        
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

stream_lock = asyncio.Lock()

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket, target: str = "", mock: str = "false"):
    try:
        await websocket.accept()
    except (WebSocketDisconnect, RuntimeError):
        return
        
    is_mock = str(mock).lower() == "true"
    if is_mock:
        return

    # Enable native Android touch indicators so that user interactions are visible in the frontend and recordings!
    try:
        await asyncio.to_thread(subprocess.run, ["adb", "shell", "settings", "put", "system", "show_touches", "1"], timeout=2)
    except:
        pass
        
    process = None
    scrcpy_proc = None
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
            
        async with stream_lock:
            # Kill any zombie scrcpy instances on the PC to prevent port conflicts!
            try:
                subprocess.run(["taskkill", "/F", "/IM", "scrcpy.exe"], capture_output=True, timeout=2)
                subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"], capture_output=True, timeout=2)
                await asyncio.sleep(0.1)
            except:
                pass

            is_landscape = False
            try:
                adb_out = await asyncio.to_thread(subprocess.check_output, ["adb", "shell", "dumpsys", "input"], text=True, timeout=3)
                for line in adb_out.splitlines():
                    if "SurfaceOrientation" in line:
                        val = line.split(":")[1].strip()
                        if val in ["1", "3"]:
                            is_landscape = True
                        break
            except Exception as e:
                print(f"Failed to get orientation via ADB: {e}")

            # Calculate precise window bounds to prevent letterboxing (black bars) which breaks touch coordinates,
            # while ensuring scrcpy creates a proper window for ffmpeg to grab.
            # Window dimensions are no longer forced, scrcpy will automatically size the window based on the device aspect ratio.
            # Use -m 700 to guarantee the window height fits entirely even on a small 1366x768 laptop screen!
            # If the window is truncated by the OS, gdigrab captures a cropped video, breaking coordinates and aspect ratio.
            scrcpy_cmd = ["scrcpy", "-m", "700", "-b", "16M", "--max-fps=30", "--render-driver=software", "--window-title", "PerfHub_Scrcpy", "--no-audio", "--window-borderless"]


            print(f"Spawning new scrcpy window (Landscape: {is_landscape})...")
            scrcpy_proc = subprocess.Popen(scrcpy_cmd)
            
            # Wait dynamically for the scrcpy window to appear (up to 5 seconds)
            window_found = False
            scrcpy_hwnd = 0
            for _ in range(50):
                def enum_cb_wait(h, _):
                    nonlocal window_found, scrcpy_hwnd
                    import ctypes
                    length = ctypes.windll.user32.GetWindowTextLengthW(h)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(h, buff, length + 1)
                        title = buff.value
                        if "PerfHub_Scrcpy" in title and "Visual Studio" not in title and "Code" not in title and "Command Prompt" not in title and "PowerShell" not in title:
                            # Verify this window belongs to our newly spawned scrcpy process!
                            pid = ctypes.c_ulong()
                            ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                            if pid.value == scrcpy_proc.pid:
                                window_found = True
                                scrcpy_hwnd = h
                                return False
                    return True
                
                import ctypes
                CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
                ctypes.windll.user32.EnumWindows(CMPFUNC(enum_cb_wait), 0)
                
                if window_found:
                    await asyncio.sleep(0.5) # Wait for window to fully initialize before ffmpeg grabs it
                    break
                await asyncio.sleep(0.1)
                
            if not window_found:
                print("Error: scrcpy window did not appear within 5 seconds. Aborting stream.")
                if scrcpy_proc:
                    scrcpy_proc.kill()
                return
            
            # Capture the window using ffmpeg gdigrab and output raw H.264
            # We use the ADB orientation detected earlier. No need for GetClientRect here anymore.        
            # Ensure dimensions are even for libx264, but DO NOT pad or force a fixed resolution,
            # otherwise the touch coordinates on the frontend will be misaligned due to black bars!
            vf_scale = "scale='trunc(iw/2)*2':'trunc(ih/2)*2'"

            ffmpeg_cmd = [
                "ffmpeg", "-loglevel", "warning", "-f", "gdigrab", "-framerate", "30", "-i", "title=PerfHub_Scrcpy", 
                "-vf", vf_scale, 
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-maxrate", "16M",
                "-bufsize", "32M",
                "-pix_fmt", "yuv420p",
                "-f", "h264", "pipe:1"
            ]
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
                        # Only print to backend console, don't flood frontend with benign ffmpeg/scrcpy warnings
                        # await websocket.send_text(f"[{name} Err] {err_msg}")
                        pass
                    except:
                        pass
            except:
                pass
                
        asyncio.create_task(drain_stderr(scrcpy_proc, "Scrcpy"))
        asyncio.create_task(drain_stderr(process, "Stream"))
            
        # Monitor for orientation changes using ADB
        async def monitor_orientation():
            try:
                while True:
                    await asyncio.sleep(2)
                    try:
                        adb_out = await asyncio.to_thread(subprocess.check_output, ["adb", "shell", "dumpsys", "input"], text=True, timeout=2)
                        current_is_landscape = False
                        for line in adb_out.split('\n'):
                            if "SurfaceOrientation" in line:
                                val = line.split(':')[1].strip()
                                if val in ["1", "3"]:
                                    current_is_landscape = True
                                break
                        if current_is_landscape != is_landscape:
                            print(f"Orientation changed via ADB! (Landscape: {current_is_landscape}). Restarting stream.")
                            if process:
                                process.terminate()
                            break
                    except Exception as e:
                        pass
            except Exception:
                pass
                
        monitor_task = asyncio.create_task(monitor_orientation())
            
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
                
        monitor_task.cancel()
                
    except WebSocketDisconnect:
        print("Stream client disconnected")
    except Exception as e:
        print(f"Stream outer error: {e}")
    finally:
        if process:
            try:
                process.terminate()
                process.kill() # Ensure it's dead, non-blocking
            except:
                pass
        if scrcpy_proc:
            try:
                scrcpy_proc.terminate()
                scrcpy_proc.kill() # Ensure it's dead, non-blocking
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
