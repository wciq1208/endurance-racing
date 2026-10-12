"""Cross-platform ownership checks and shutdown for token-tagged collectors."""
import os
from pathlib import Path
import time
import psutil


def detached_options(system=None):
    if (system or os.name) == 'nt':
        # Constants are numeric so this branch can also be verified on POSIX.
        return {'creationflags': 0x00000008 | 0x00000200}  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    return {'start_new_session': True}


def matches(argv, token, scripts):
    if not token or len(argv) < 2 or '--token' not in argv:
        return False
    i = argv.index('--token')
    if i + 1 >= len(argv) or argv[i + 1] != token:
        return False
    # All collectors are launched as: interpreter absolute-script-path ...
    return os.path.normcase(str(Path(argv[1]).resolve())) in {
        os.path.normcase(str(Path(s).resolve())) for s in scripts
    }


def owned_processes(state, scripts):
    if not state or not state.get('token'):
        return []
    found = []
    for proc in psutil.process_iter():
        try:
            if matches(proc.cmdline(), state['token'], scripts):
                if proc.status() != psutil.STATUS_ZOMBIE:
                    found.append(proc)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except psutil.AccessDenied:
            # Refuse cleanup if the recorded supervisor cannot be inspected.
            if proc.pid == state.get('pid', state.get('pgid')):
                raise
    return found


def stop_owned(state, scripts):
    stopped = False
    deadline = time.monotonic() + 12
    while True:
        processes = owned_processes(state, scripts)
        if not processes:
            return stopped
        if time.monotonic() >= deadline:
            raise RuntimeError('旧采集进程未全部退出，拒绝删除产出')
        # Freeze producers before terminating, preventing replacement children.
        suspended = []
        try:
            for proc in processes:
                try:
                    proc.suspend()
                    suspended.append(proc)
                except psutil.NoSuchProcess:
                    pass
            for proc in processes:
                try:
                    proc.kill()
                    stopped = True
                except psutil.NoSuchProcess:
                    pass
        except Exception:
            # A denied termination must not leave surviving collectors frozen.
            for proc in suspended:
                try:
                    proc.resume()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            raise
        _, alive = psutil.wait_procs(processes, timeout=3)
        if alive:
            time.sleep(.1)
        # Rescan for orphaned one-shots spawned just before suspension.
