import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from channel.wechat_group import wechat_group_client as client_module
from channel.wechat_group.protocol import SidecarCommandType


WechatGroupClient = client_module.WechatGroupClient


class FakeStdin:
    def __init__(self, events=None):
        self.lines = []
        self.events = events if events is not None else []

    def write(self, value):
        self.lines.append(value)
        self.events.append("write")

    def flush(self):
        self.events.append("flush")


class FakeProcess:
    def __init__(self, wait_results=None, events=None):
        self.events = events if events is not None else []
        self.stdin = FakeStdin(self.events)
        self.stdout = []
        self.stderr = []
        self.returncode = None
        self.wait_results = list(wait_results or [0])
        self.wait_timeouts = []
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.events.append("wait")
        self.wait_timeouts.append(timeout)
        result = self.wait_results.pop(0)
        if result == "timeout":
            raise subprocess.TimeoutExpired("node", timeout)
        if isinstance(result, BaseException):
            raise result
        self.returncode = result
        return result

    def terminate(self):
        self.events.append("terminate")
        self.terminate_calls += 1

    def kill(self):
        self.events.append("kill")
        self.kill_calls += 1


class WechatGroupClientPathTest(unittest.TestCase):
    def _helpers(self):
        prefix_helper = getattr(
            client_module,
            "get_wechat_group_sidecar_memory_prefix",
            None,
        )
        file_helper = getattr(
            client_module,
            "get_wechat_group_memory_card_file_path",
            None,
        )
        self.assertIsNotNone(prefix_helper)
        self.assertIsNotNone(file_helper)
        return prefix_helper, file_helper

    def test_legacy_memory_path_helper_returns_effective_prefix(self):
        legacy_helper = getattr(
            client_module,
            "get_wechat_group_sidecar_memory_path",
            None,
        )
        self.assertIsNotNone(legacy_helper)
        with tempfile.TemporaryDirectory() as temp_dir:
            configured_prefix = os.path.join(temp_dir, "wechat_group")
            with patch(
                "channel.wechat_group.wechat_group_client.conf",
                return_value={"wechat_group_sidecar_memory_path": configured_prefix},
            ):
                expected_prefix = os.path.abspath(configured_prefix)
                self.assertEqual(
                    expected_prefix,
                    legacy_helper(),
                )
                self.assertEqual(
                    expected_prefix,
                    client_module.get_wechat_group_sidecar_memory_prefix(),
                )

    def test_default_memory_prefix_and_file_path_are_absolute(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = os.path.join(temp_dir, "home")

            def expand_user(path):
                return path.replace("~", home, 1) if path.startswith("~") else path

            with patch(
                "channel.wechat_group.wechat_group_client.conf",
                return_value={},
            ), patch(
                "channel.wechat_group.wechat_group_client.os.path.expanduser",
                side_effect=expand_user,
            ):
                prefix_helper, file_helper = self._helpers()
                expected_prefix = os.path.abspath(
                    os.path.join(home, ".lightagent", "wechat_group")
                )
                self.assertEqual(
                    expected_prefix,
                    prefix_helper(),
                )
                self.assertEqual(
                    expected_prefix + ".memory-card.json",
                    file_helper(),
                )

    def test_custom_memory_prefix_expands_user_and_becomes_absolute(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = os.path.join(temp_dir, "home")
            configured_prefix = os.path.join("~", "sessions", "wechat")

            def expand_user(path):
                return path.replace("~", home, 1) if path.startswith("~") else path

            with patch(
                "channel.wechat_group.wechat_group_client.conf",
                return_value={"wechat_group_sidecar_memory_path": configured_prefix},
            ), patch(
                "channel.wechat_group.wechat_group_client.os.path.expanduser",
                side_effect=expand_user,
            ):
                prefix_helper, file_helper = self._helpers()
                expected_prefix = os.path.abspath(
                    os.path.join(home, "sessions", "wechat")
                )
                self.assertEqual(
                    expected_prefix,
                    prefix_helper(),
                )
                self.assertEqual(
                    expected_prefix + ".memory-card.json",
                    file_helper(),
                )

    def test_memory_file_path_does_not_duplicate_existing_suffix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            configured_path = os.path.join(
                temp_dir,
                "wechat_group.memory-card.json",
            )
            with patch(
                "channel.wechat_group.wechat_group_client.conf",
                return_value={"wechat_group_sidecar_memory_path": configured_path},
            ):
                prefix_helper, file_helper = self._helpers()
                expected_path = os.path.abspath(configured_path)
                self.assertEqual(
                    expected_path,
                    prefix_helper(),
                )
                self.assertEqual(
                    expected_path,
                    file_helper(),
                )


class WechatGroupClientLifecycleTest(unittest.TestCase):
    def _start_twice_with_deferred_threads(self, event_handler=None):
        deferred_threads = []

        class DeferredThread:
            def __init__(self, target, args=(), daemon=None):
                self.target = target
                self.args = args
                self.daemon = daemon
                deferred_threads.append(self)

            def start(self):
                return None

            def run(self):
                self.target(*self.args)

        old_process = FakeProcess()
        old_process.stdout = ['{"type":"status","status":"old"}\n']
        old_process.stderr = ["old stderr\n"]
        new_process = FakeProcess()
        new_process.stdout = ['{"type":"status","status":"new"}\n']
        new_process.stderr = ["new stderr\n"]
        client = WechatGroupClient(event_handler=event_handler)

        with patch.object(client, "_build_command", return_value=["node"]), patch.object(
            client,
            "_sidecar_dir",
            return_value=os.getcwd(),
        ), patch(
            "channel.wechat_group.wechat_group_client.subprocess.Popen",
            side_effect=[old_process, new_process],
        ), patch(
            "channel.wechat_group.wechat_group_client.threading.Thread",
            DeferredThread,
        ):
            client.start()
            old_process.returncode = 0
            client.start()

        return client, old_process, new_process, deferred_threads

    def test_stop_sends_stop_and_waits_for_normal_exit(self):
        process = FakeProcess()
        client = WechatGroupClient()
        client.process = process

        client.stop()

        commands = [json.loads(line) for line in process.stdin.lines]
        self.assertEqual([{"type": "stop"}], commands)
        self.assertEqual(1, len(process.wait_timeouts))
        self.assertIsNotNone(process.wait_timeouts[0])
        self.assertEqual(0, process.terminate_calls)
        self.assertEqual(0, process.kill_calls)
        self.assertIsNone(client.process)

    def test_stop_terminates_then_kills_after_two_timeouts(self):
        process = FakeProcess(wait_results=["timeout", "timeout", 0])
        client = WechatGroupClient()
        client.process = process

        client.stop()

        self.assertEqual(1, process.terminate_calls)
        self.assertEqual(1, process.kill_calls)
        self.assertEqual(3, len(process.wait_timeouts))
        self.assertTrue(all(timeout is not None for timeout in process.wait_timeouts))
        self.assertEqual(
            ["write", "flush", "wait", "terminate", "wait", "kill", "wait"],
            process.events,
        )
        self.assertIsNone(client.process)

    def test_stop_keeps_process_reference_when_kill_wait_times_out(self):
        process = FakeProcess(wait_results=["timeout", "timeout", "timeout"])
        client = WechatGroupClient()
        client.process = process

        with self.assertRaises(subprocess.TimeoutExpired):
            client.stop()

        self.assertEqual(1, process.terminate_calls)
        self.assertEqual(1, process.kill_calls)
        self.assertIs(process, client.process)

    def test_stop_keeps_process_reference_when_kill_wait_raises_os_error(self):
        process = FakeProcess(
            wait_results=["timeout", "timeout", OSError("wait failed")]
        )
        client = WechatGroupClient()
        client.process = process

        with self.assertRaisesRegex(OSError, "wait failed"):
            client.stop()

        self.assertEqual(1, process.terminate_calls)
        self.assertEqual(1, process.kill_calls)
        self.assertIs(process, client.process)

    def test_stop_is_idempotent(self):
        process = FakeProcess()
        client = WechatGroupClient()
        client.process = process

        client.stop()
        client.stop()

        self.assertEqual(1, len(process.stdin.lines))
        self.assertEqual(1, len(process.wait_timeouts))
        self.assertIsNone(client.process)

    def test_start_and_stop_are_serialized(self):
        process = FakeProcess()
        popen_entered = threading.Event()
        allow_popen_to_finish = threading.Event()
        stop_attempted = threading.Event()
        stop_finished = threading.Event()

        def create_process(*args, **kwargs):
            popen_entered.set()
            allow_popen_to_finish.wait(timeout=2)
            return process

        client = WechatGroupClient()

        def stop_client():
            stop_attempted.set()
            client.stop()
            stop_finished.set()

        with patch.object(client, "_build_command", return_value=["node"]), patch.object(
            client,
            "_sidecar_dir",
            return_value=os.getcwd(),
        ), patch(
            "channel.wechat_group.wechat_group_client.subprocess.Popen",
            side_effect=create_process,
        ):
            start_thread = threading.Thread(target=client.start)
            stop_thread = threading.Thread(target=stop_client)
            start_thread.start()
            self.assertTrue(popen_entered.wait(timeout=1))
            stop_thread.start()
            self.assertTrue(stop_attempted.wait(timeout=1))
            try:
                self.assertFalse(stop_finished.wait(timeout=0.1))
            finally:
                allow_popen_to_finish.set()
                start_thread.join(timeout=2)
                stop_thread.join(timeout=2)

        self.assertFalse(start_thread.is_alive())
        self.assertFalse(stop_thread.is_alive())
        self.assertIsNone(client.process)

    def test_send_command_revalidates_process_after_waiting_for_lifecycle_lock(self):
        process = FakeProcess()
        client = WechatGroupClient()
        client.process = process
        dump_reached = threading.Event()
        errors = []
        original_dumps = json.dumps

        def signal_dump(*args, **kwargs):
            dump_reached.set()
            return original_dumps(*args, **kwargs)

        def send_command():
            try:
                client.list_rooms()
            except Exception as e:
                errors.append(e)

        sender = threading.Thread(target=send_command)
        with patch(
            "channel.wechat_group.wechat_group_client.json.dumps",
            side_effect=signal_dump,
        ):
            client._lock.acquire()
            try:
                sender.start()
                self.assertTrue(dump_reached.wait(timeout=1))
                client.process = None
            finally:
                client._lock.release()
            sender.join(timeout=2)

        self.assertFalse(sender.is_alive())
        self.assertEqual(1, len(errors))
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertEqual("wechat group sidecar is not started", str(errors[0]))

    def test_send_command_flushes_captured_stdin_when_process_reference_changes(self):
        client = WechatGroupClient()
        old_process = FakeProcess()
        new_process = FakeProcess()

        class SwitchingStdin(FakeStdin):
            def write(self, value):
                super().write(value)
                client.process = new_process

        old_process.stdin = SwitchingStdin(old_process.events)
        client.process = old_process

        client.list_rooms()

        self.assertEqual(["write", "flush"], old_process.events)
        self.assertEqual([], new_process.events)
        self.assertEqual(
            [{"type": "list_rooms"}],
            [json.loads(line) for line in old_process.stdin.lines],
        )

    def test_delayed_reader_thread_reads_original_process_stdout(self):
        statuses = []
        client, old_process, new_process, threads = self._start_twice_with_deferred_threads(
            event_handler=lambda event: statuses.append(event.get("status"))
        )

        threads[0].run()

        self.assertIs(new_process, client.process)
        self.assertEqual(["old"], statuses)

    def test_delayed_stderr_thread_reads_original_process_stderr(self):
        client, old_process, new_process, threads = self._start_twice_with_deferred_threads()

        with patch.object(client_module.logger, "warning") as warning:
            threads[1].run()

        self.assertIs(new_process, client.process)
        warning.assert_called_once_with("[wechat_group] sidecar stderr: old stderr")

    def test_client_has_no_in_process_relogin_command(self):
        self.assertFalse(hasattr(WechatGroupClient(), "relogin"))

    def test_protocol_has_no_in_process_relogin_command(self):
        self.assertFalse(hasattr(SidecarCommandType, "RELOGIN"))


class WechatGroupClientForceRescanTest(unittest.TestCase):
    def test_force_rescan_stops_deletes_only_cache_file_then_starts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prefix = os.path.join(temp_dir, "wechat_group")
            cache_path = Path(prefix + ".memory-card.json")
            other_path = Path(temp_dir, "identity.db")
            media_path = Path(temp_dir, "media")
            cache_path.write_text('{"session": true}', encoding="utf-8")
            other_path.write_text("keep", encoding="utf-8")
            media_path.mkdir()
            process = FakeProcess()
            client = WechatGroupClient()
            client.process = process
            start_observations = []

            def observe_start():
                start_observations.append(
                    (client.process, cache_path.exists(), other_path.exists(), media_path.exists())
                )

            with patch(
                "channel.wechat_group.wechat_group_client.conf",
                return_value={"wechat_group_sidecar_memory_path": prefix},
            ), patch.object(client, "start", side_effect=observe_start) as start:
                self.assertTrue(hasattr(client, "force_rescan"))
                client.force_rescan()

            start.assert_called_once_with()
            self.assertEqual([(None, False, True, True)], start_observations)
            self.assertFalse(cache_path.exists())
            self.assertTrue(other_path.exists())
            self.assertTrue(media_path.exists())

    def test_force_rescan_succeeds_when_cache_file_does_not_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prefix = os.path.join(temp_dir, "missing")
            client = WechatGroupClient()
            client.stop = Mock()
            client.start = Mock()

            with patch(
                "channel.wechat_group.wechat_group_client.conf",
                return_value={"wechat_group_sidecar_memory_path": prefix},
            ):
                self.assertTrue(hasattr(client, "force_rescan"))
                client.force_rescan()

            client.stop.assert_called_once_with()
            client.start.assert_called_once_with()

    def test_force_rescan_restarts_old_connection_after_delete_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prefix = os.path.join(temp_dir, "wechat_group")
            events = []
            client = WechatGroupClient()
            client.stop = Mock(side_effect=lambda: events.append("stop"))
            client.start = Mock(side_effect=lambda: events.append("start"))

            def deny_delete(path):
                events.append(("delete", path))
                raise PermissionError("access denied")

            with patch(
                "channel.wechat_group.wechat_group_client.conf",
                return_value={"wechat_group_sidecar_memory_path": prefix},
            ), patch(
                "channel.wechat_group.wechat_group_client.os.remove",
                side_effect=deny_delete,
            ):
                self.assertTrue(hasattr(client, "force_rescan"))
                with self.assertRaisesRegex(
                    RuntimeError,
                    "failed to remove WeChat group login cache",
                ) as error:
                    client.force_rescan()

            expected_path = os.path.abspath(prefix) + ".memory-card.json"
            self.assertEqual(
                ["stop", ("delete", expected_path), "start"],
                events,
            )
            self.assertIsInstance(error.exception.__cause__, PermissionError)


if __name__ == "__main__":
    unittest.main()
