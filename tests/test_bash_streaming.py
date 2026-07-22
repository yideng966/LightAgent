import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from agent.tools.bash.bash import Bash


posix_only = pytest.mark.skipif(Bash._IS_WIN, reason="POSIX shell command")
windows_only = pytest.mark.skipif(not Bash._IS_WIN, reason="Windows integration test")


def _windows_pid_command(pid_file):
    path = str(pid_file).replace("\\", "\\\\")
    return (
        f'"{sys.executable}" -c '
        f'"import os,time;open(r\'{path}\',\'w\').write(str(os.getpid()));time.sleep(30)"'
    )


def _windows_pid_is_running(pid):
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return f'"{pid}"' in result.stdout


def _windows_kill_pid_file(pid_file):
    if pid_file.exists():
        subprocess.run(
            ["taskkill", "/F", "/PID", pid_file.read_text()],
            capture_output=True,
        )


@posix_only
def test_fast_command_returns_output_without_progress(tmp_path):
    tool = Bash({"cwd": str(tmp_path)})
    progress = []
    tool.progress_callback = progress.append

    result = tool.execute({"command": "printf fast"})

    assert result.status == "success"
    assert result.result["output"] == "fast"
    assert progress == []


@posix_only
def test_timeout_returns_promptly(tmp_path):
    tool = Bash({"cwd": str(tmp_path)})
    started = time.monotonic()

    result = tool.execute({"command": "sleep 10", "timeout": 1})

    assert result.status == "error"
    assert "timed out after 1 seconds" in result.result
    assert time.monotonic() - started < 3


@posix_only
def test_background_process_holding_pipe_does_not_hang(tmp_path):
    tool = Bash({"cwd": str(tmp_path)})
    started = time.monotonic()

    result = tool.execute({"command": "sleep 10 & printf done", "timeout": 3})

    assert result.status == "success"
    assert result.result["output"] == "done"
    assert time.monotonic() - started < 7


@posix_only
def test_output_without_trailing_newline_streams_progress(tmp_path):
    tool = Bash({"cwd": str(tmp_path)})
    progress = []
    tool.progress_callback = progress.append

    result = tool.execute({
        "command": "for i in 1 2 3 4 5; do printf .; sleep 0.3; done",
        "timeout": 5,
    })

    assert result.status == "success"
    assert result.result["output"] == "....."
    assert progress
    assert progress[-1].endswith(".")


def test_windows_kill_uses_taskkill_for_process_tree():
    tool = Bash()
    process = type("Process", (), {"pid": 1234, "poll": lambda self: None, "kill": lambda self: None})()

    with patch.object(tool, "_IS_WIN", True), patch.object(subprocess, "run") as run:
        run.return_value.returncode = 0
        tool._kill_process(process)

    run.assert_called_once_with(
        ["taskkill", "/F", "/T", "/PID", "1234"],
        capture_output=True,
        timeout=5,
    )


def test_windows_kill_falls_back_when_taskkill_fails():
    tool = Bash()
    process = type("Process", (), {"pid": 1234, "poll": lambda self: None, "kill": lambda self: None})()

    with patch.object(tool, "_IS_WIN", True), \
            patch.object(subprocess, "run", side_effect=OSError), \
            patch.object(process, "kill") as kill:
        tool._kill_process(process)

    kill.assert_called_once()


@windows_only
def test_windows_timeout_kills_process_tree(tmp_path):
    pid_file = tmp_path / "timeout-child.pid"
    child_command = _windows_pid_command(pid_file)
    tool = Bash({"cwd": str(tmp_path)})
    started = time.monotonic()

    try:
        result = tool.execute({
            "command": f'start "" /b {child_command} & ping -n 30 127.0.0.1 >nul',
            "timeout": 1,
        })

        assert result.status == "error"
        assert "timed out after 1 seconds" in result.result
        assert time.monotonic() - started < 8
        assert pid_file.exists()
        time.sleep(0.5)
        assert not _windows_pid_is_running(pid_file.read_text())
    finally:
        _windows_kill_pid_file(pid_file)


@windows_only
def test_windows_long_running_command_streams_progress(tmp_path):
    tool = Bash({"cwd": str(tmp_path)})
    progress = []
    tool.progress_callback = progress.append

    result = tool.execute({
        "command": (
            f'"{sys.executable}" -u -c '
            '"import sys,time; '
            "[(sys.stdout.write('.'),sys.stdout.flush(),time.sleep(0.3)) "
            'for _ in range(5)]"'
        ),
        "timeout": 5,
    })

    assert result.status == "success"
    assert result.result["output"] == "....."
    assert progress
    assert progress[-1].endswith(".")


@windows_only
def test_windows_background_process_holding_pipe_does_not_hang(tmp_path):
    pid_file = tmp_path / "background-child.pid"
    child_command = _windows_pid_command(pid_file)
    tool = Bash({"cwd": str(tmp_path)})
    started = time.monotonic()

    try:
        result = tool.execute({
            "command": f'start "" /b {child_command} & echo done',
            "timeout": 3,
        })

        assert result.status == "success"
        assert result.result["output"].strip() == "done"
        assert time.monotonic() - started < 8
        assert pid_file.exists()
    finally:
        _windows_kill_pid_file(pid_file)
