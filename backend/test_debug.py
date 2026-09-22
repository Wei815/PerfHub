import subprocess

scrcpy_path = r'C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Genymobile.scrcpy_Microsoft.Winget.Source_8wekyb3d8bbwe\scrcpy-win64-v4.1\scrcpy.exe'
cmd = [scrcpy_path, '-V', 'debug', '-m', '1024', '-b', '2M', '--no-window', '--no-audio', '--video-codec=h264', '--record-format=mkv', '--record=-']

try:
    p = subprocess.run(cmd, capture_output=True, timeout=5)
    print("Stdout len:", len(p.stdout))
    print(p.stderr.decode('utf-8', errors='ignore'))
except subprocess.TimeoutExpired as e:
    print("Timeout! Stdout len:", len(e.stdout) if e.stdout else 0)
    if e.stderr:
        print(e.stderr.decode('utf-8', errors='ignore'))
    else:
        print("No stderr captured.")
