import ctypes
found = []
def enum_cb_wait(h, _):
    length = ctypes.windll.user32.GetWindowTextLengthW(h)
    if length > 0:
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(h, buff, length + 1)
        if "PerfHub_Scrcpy" in buff.value:
            found.append(buff.value)
    return True
CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
ctypes.windll.user32.EnumWindows(CMPFUNC(enum_cb_wait), 0)
print("Found windows:", found)
