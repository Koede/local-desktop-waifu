import os, subprocess, atexit, threading, asyncio, json, sys, urllib.request
from colorama import *

import utils.dependencies
import utils.multi_thread

# Run voicevox. None unless this process spawned the engine.
process = None

def kill_process():
    global process
    if process is None:
        return
    print(Fore.RED + "voicevox terminating" + Fore.RESET, flush=True)
    try:
        process.terminate()
        
    except:
        pass

def handle_output(stream, suffix):
    while True:
        line = stream.readline()
        if not line:
            break
        print(Style.DIM + f"voicevox: {line.decode().rstrip()}" + Style.RESET_ALL)

def start():
    global process

    url = os.environ.get("VOICEVOX_URL") or "http://127.0.0.1:50021"

    try:
        with urllib.request.urlopen(f"{url}/version", timeout=2) as response:
            if 200 <= response.status < 300:
                print(Fore.GREEN + f"Voicevox engine is already up at {url}" + Fore.RESET, flush=True)
                return
    except Exception:
        pass

    exe = utils.dependencies.VOICEVOX_DIR + "/run.exe"
    if sys.platform == "win32" and os.path.exists(exe):
        process = subprocess.Popen(
            exe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        atexit.register(kill_process)

        if json.loads(os.environ.get("VOICEVOX_LOG",  "False").lower()):
            tasks = [
                threading.Thread(target=handle_output, args=(process.stdout, "stdout")),
                threading.Thread(target=handle_output, args=(process.stderr, "stderr")),
            ]

            for task in tasks:
                task.start()

            for task in tasks:
                task.join()
    else:
        print(Fore.YELLOW + f"Voicevox must already be running at {url}" + Fore.RESET, flush=True)

    # return process.wait()

def run_async():
    utils.multi_thread.run_in_new_thread(start)

    # return await process.wait()

from concurrent.futures import ThreadPoolExecutor
