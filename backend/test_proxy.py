import subprocess
import time
import os

scrcpy_cmd = ['scrcpy', '-V', 'error', '-m', '1024', '-b', '2M', '--no-window', '--no-audio', '--video-codec=h264', '--record-format=mkv', '--record=-']
ffmpeg_cmd = ['ffmpeg', '-loglevel', 'warning', '-i', 'pipe:0', '-c:v', 'copy', '-f', 'h264', '-flush_packets', '1', 'pipe:1']

try:
    subprocess.run(["taskkill", "/F", "/IM", "scrcpy.exe"], capture_output=True, timeout=2)
except: pass

scrcpy_proc = subprocess.Popen(scrcpy_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

with open("proxy_log.txt", "w") as f:
    f.write("Starting...\n")
    f.flush()

    # Read from scrcpy stdout until we find MKV header
    buf = b""
    found_mkv = False
    while not found_mkv:
        char = scrcpy_proc.stdout.read(1)
        if not char:
            f.write("EOF reached without MKV header!\n")
            break
        buf += char
        if b"\x1A\x45\xDF\xA3" in buf:
            found_mkv = True
            f.write(f"Found MKV header after {len(buf)} bytes. Skipped: {repr(buf[:-4])}\n")
            f.flush()
            break

    if not found_mkv:
        f.write("MKV header not found!\n")
        f.flush()
        exit(1)

    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    ffmpeg_proc.stdin.write(b"\x1A\x45\xDF\xA3") # Write the header we consumed
    ffmpeg_proc.stdin.flush()
    f.write("Wrote MKV header to ffmpeg\n")
    f.flush()

    import threading
    def pump():
        while True:
            chunk = scrcpy_proc.stdout.read(65536)
            if not chunk: break
            ffmpeg_proc.stdin.write(chunk)
            ffmpeg_proc.stdin.flush()
            
    t = threading.Thread(target=pump, daemon=True)
    t.start()
    
    try:
        ffmpeg_out = ffmpeg_proc.stdout.read(1024)
        f.write(f"FFmpeg output length: {len(ffmpeg_out)}\n")
        f.write(f"FFmpeg stderr: {repr(ffmpeg_proc.stderr.read(1024))}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
    f.flush()

scrcpy_proc.kill()
ffmpeg_proc.kill()
