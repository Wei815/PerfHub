import ctypes
import subprocess
import time

try:
    out = subprocess.check_output(['tasklist', '/fi', 'imagename eq scrcpy.exe', '/fo', 'csv', '/nh'], text=True)
    pids = [line.split(',')[1].strip('\"') for line in out.splitlines() if 'scrcpy.exe' in line]
    if not pids:
        print('No scrcpy running.')
        exit(0)
    pid = int(pids[0])
    print(f'Scrcpy PID: {pid}')
    
    def enum_cb(h, _):
        pid_ptr = ctypes.c_int()
        ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(pid_ptr))
        if pid_ptr.value == pid:
            length = ctypes.windll.user32.GetWindowTextLengthW(h)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(h, buff, length + 1)
                print(f'Window title for scrcpy PID {pid}: \"{buff.value}\"')
        return True
    
    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    ctypes.windll.user32.EnumWindows(CMPFUNC(enum_cb), 0)
except Exception as e:
    print(e)
