"""Keep CaptureGPT running by restarting it after it exits."""

import subprocess
import sys
import time
import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
APP_EXE = APP_DIR / "CaptureGPT.exe"
SOURCE_ENTRY_POINT = APP_DIR / "main.pyw"
RESTART_DELAY_SECONDS = 2
NO_USER_SESSION_RETRY_SECONDS = 5


def get_app_command() -> list[str]:
    """Prefer the packaged app beside this script, otherwise run from source."""
    if APP_EXE.is_file():
        return [str(APP_EXE)]

    if SOURCE_ENTRY_POINT.is_file():
        return [sys.executable, str(SOURCE_ENTRY_POINT)]

    raise FileNotFoundError(
        f"Could not find {APP_EXE.name} or {SOURCE_ENTRY_POINT.name} in {APP_DIR}"
    )


def get_windows_modules():
    """Load Windows session APIs only when the watchdog needs them."""
    try:
        import psutil
        import win32api
        import win32con
        import win32event
        import win32profile
        import win32process
        import win32ts
    except ImportError as error:
        raise RuntimeError(
            "Service session support requires pywin32 and psutil."
        ) from error

    return (
        psutil,
        win32api,
        win32con,
        win32event,
        win32profile,
        win32process,
        win32ts,
    )


def get_active_user_session(win32ts):
    """Prefer the active console session, then an active RDP session."""
    sessions = win32ts.WTSEnumerateSessions(None, 0, 1)
    active_ids = [
        session["SessionId"]
        for session in sessions
        if session["State"] == win32ts.WTSActive and session["SessionId"] != 0
    ]
    console_id = win32ts.WTSGetActiveConsoleSessionId()
    if console_id in active_ids:
        return console_id
    return active_ids[0] if active_ids else None


def get_watchdog_session_id(win32ts) -> int:
    return win32ts.ProcessIdToSessionId(os.getpid())


def find_running_app(session_id: int, modules):
    """Find an existing packaged app in the target session."""
    psutil, _api, _con, _event, _profile, _process, win32ts = modules
    expected_name = APP_EXE.name.casefold()
    for process in psutil.process_iter(["name"]):
        try:
            if (
                (process.info["name"] or "").casefold() == expected_name
                and win32ts.ProcessIdToSessionId(process.pid) == session_id
            ):
                return process
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def launch_in_user_session(command: list[str], session_id: int, modules) -> int:
    """Start CaptureGPT on the logged-in user's visible Windows desktop."""
    (
        _psutil,
        _win32api,
        win32con,
        win32event,
        win32profile,
        win32process,
        win32ts,
    ) = modules

    token = win32ts.WTSQueryUserToken(session_id)
    process_handle = thread_handle = None
    environment = None
    try:
        environment = win32profile.CreateEnvironmentBlock(token, False)
        startup_info = win32process.STARTUPINFO()
        startup_info.lpDesktop = r"winsta0\default"
        command_line = subprocess.list2cmdline(command)
        process_handle, thread_handle, _pid, _tid = win32process.CreateProcessAsUser(
            token,
            command[0],
            command_line,
            None,
            None,
            False,
            win32con.CREATE_UNICODE_ENVIRONMENT,
            environment,
            str(APP_DIR),
            startup_info,
        )
    finally:
        token.Close()

    try:
        win32event.WaitForSingleObject(process_handle, win32event.INFINITE)
        return win32process.GetExitCodeProcess(process_handle)
    finally:
        process_handle.Close()
        thread_handle.Close()


def main() -> int:
    command = get_app_command()
    modules = get_windows_modules()
    psutil, win32api, win32con, win32event, _profile, win32process, win32ts = modules
    watchdog_session_id = get_watchdog_session_id(win32ts)
    running_as_service = watchdog_session_id == 0

    launch_label = (
        "the active user's desktop session"
        if running_as_service
        else f"Windows session {watchdog_session_id}"
    )
    print(f"Watching CaptureGPT in {launch_label}: {APP_DIR}")
    print("Press Ctrl+C to stop the watchdog.")

    while True:
        process = None
        try:
            if running_as_service:
                session_id = get_active_user_session(win32ts)
                if session_id is None:
                    print("No signed-in desktop session; checking again shortly.")
                    time.sleep(NO_USER_SESSION_RETRY_SECONDS)
                    continue

                running_app = find_running_app(session_id, modules)
                if running_app is not None:
                    print(
                        f"CaptureGPT is already running in session {session_id}; "
                        "watching that process."
                    )
                    try:
                        exit_code = running_app.wait()
                    except psutil.NoSuchProcess:
                        exit_code = 0
                else:
                    print(f"Starting CaptureGPT in user session {session_id}.")
                    exit_code = launch_in_user_session(command, session_id, modules)
            else:
                process = subprocess.Popen(command, cwd=APP_DIR)
                exit_code = process.wait()

            print(
                f"CaptureGPT closed (exit code {exit_code}); "
                f"restarting in {RESTART_DELAY_SECONDS} seconds..."
            )
            time.sleep(RESTART_DELAY_SECONDS)
        except KeyboardInterrupt:
            print("Stopping watchdog...")
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait()
            return 0
        except (OSError, win32api.error) as error:
            print(f"Could not start or monitor CaptureGPT: {error}", file=sys.stderr)
            time.sleep(NO_USER_SESSION_RETRY_SECONDS)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
