import ctypes
from ctypes import wintypes
def enum_cb(h, _):
    length = ctypes.windll.user32.GetWindowTextLengthW(h)
    buff = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(h, buff, length + 1)
    if 'PerfHub' in buff.value:
        rect = wintypes.RECT()
        ctypes.windll.user32.GetClientRect(h, ctypes.byref(rect))
        pid_ptr = ctypes.c_int()
        ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(pid_ptr))
        print(f'Found window! Handle: {h}, PID: {pid_ptr.value}, Title: \"{buff.value}\", ClientRect: {rect.right - rect.left}x{rect.bottom - rect.top}')
    return True
CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
ctypes.windll.user32.EnumWindows(CMPFUNC(enum_cb), 0)
