import sys
import platform
import os

prompt = sys.argv[1] if len(sys.argv) > 1 else "hello world"

print(f"Prompt: {prompt}")
print(f"Platform: {platform.system()}")
print(f"Python executable: {sys.executable}")
print(f"CWD (normalized): {os.path.abspath('.')}")
# show sample path conversion guidance
if platform.system() == 'Windows':
    print('Note: On WSL, convert C:\\ paths to /mnt/c/.. or use environment variables.')
else:
    print('Note: On Windows use C:\\... or set env vars; on WSL use /mnt/c/...')
