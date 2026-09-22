import subprocess

try:
    p = subprocess.run(['scrcpy', '-V', 'error', '-m', '1024', '-b', '2M', '--no-window', '--no-audio', '--video-codec=h264', '--record-format=mkv', '--record=-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
except subprocess.TimeoutExpired as e:
    print('STDOUT len:', len(e.stdout) if e.stdout else 0)
    print('STDOUT head:', repr(e.stdout[:32]) if e.stdout else None)
    print('STDERR:', repr(e.stderr) if e.stderr else None)
