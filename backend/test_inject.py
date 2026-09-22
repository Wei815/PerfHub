import ctypes
from ctypes import wintypes
import time

hwnd = ctypes.windll.user32.FindWindowW(None, "PerfHub_Scrcpy")
print(f"HWND: {hwnd}")

if hwnd:
    rect = wintypes.RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    print(f"Client Rect: {w}x{h}")
    
    # Click in the middle of the screen
    cx = int(w / 2)
    cy = int(h / 2)
    lparam = (cy << 16) | (cx & 0xFFFF)
    
    print(f"Injecting click at {cx}, {cy}...")
    ctypes.windll.user32.PostMessageW(hwnd, 0x0200, 0, lparam) # MOUSEMOVE
    ctypes.windll.user32.PostMessageW(hwnd, 0x0201, 1, lparam) # LBUTTONDOWN
    time.sleep(0.1)
    ctypes.windll.user32.PostMessageW(hwnd, 0x0202, 0, lparam) # LBUTTONUP
    print("Injected!")
else:
    print("Window not found!")
