import ctypes
import subprocess
from ctypes import wintypes
out = subprocess.check_output(['tasklist', '/fi', 'imagename eq scrcpy.exe', '/fo', 'csv', '/nh'], text=True)
pids = [line.split(',')[1].strip('\"') for line in out.splitlines() if 'scrcpy.exe' in line]
if not pids:
    print('no scrcpy')
    exit(0)
pid = int(pids[0])
print(f'Scrcpy PID: {pid}')

found_hwnds = []
def enum_cb(h, _):
    pid_ptr = ctypes.c_int()
    ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(pid_ptr))
    if pid_ptr.value == pid:
        length = ctypes.windll.user32.GetWindowTextLengthW(h)
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(h, buff, length + 1)
        
        rect = wintypes.RECT()
        ctypes.windll.user32.GetClientRect(h, ctypes.byref(rect))
        print(f'Window handle {h}, title: \"{buff.value}\", ClientRect: {rect.right - rect.left}x{rect.bottom - rect.top}')
        found_hwnds.append(h)
    return True
CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
ctypes.windll.user32.EnumWindows(CMPFUNC(enum_cb), 0)

if not found_hwnds:
    print('No windows found for scrcpy!')
