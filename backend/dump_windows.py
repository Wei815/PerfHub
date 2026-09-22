import ctypes

def get_windows():
    found = []
    def enum_cb(h, _):
        length = ctypes.windll.user32.GetWindowTextLengthW(h)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(h, buff, length + 1)
            
            class_buff = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(h, class_buff, 256)
            
            # Print any window related to scrcpy or PerfHub
            if "scrcpy" in buff.value.lower() or "perfhub" in buff.value.lower() or "sdl" in class_buff.value.lower():
                found.append((h, buff.value, class_buff.value))
        return True
    
    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    ctypes.windll.user32.EnumWindows(CMPFUNC(enum_cb), 0)
    return found

import json
windows = get_windows()
with open("windows.json", "w", encoding="utf-8") as f:
    json.dump(windows, f, indent=2, ensure_ascii=False)
