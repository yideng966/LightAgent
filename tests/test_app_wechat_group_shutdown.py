import unittest
from unittest.mock import Mock, patch

import app
from common import const


class AppWechatGroupShutdownTest(unittest.TestCase):
    def setUp(self):
        self._original_channel_manager = app._channel_mgr

    def tearDown(self):
        app._channel_mgr = self._original_channel_manager

    def test_cleanup_skips_when_manager_or_wechat_group_channel_is_missing(self):
        app._stop_wechat_group_channel(None)

        manager = Mock()
        manager.get_channel.return_value = None

        app._stop_wechat_group_channel(manager)

        manager.get_channel.assert_called_once_with(const.WECHAT_GROUP)
        manager.stop.assert_not_called()

    def test_cleanup_stops_only_existing_wechat_group_channel(self):
        manager = Mock()
        manager.get_channel.return_value = object()

        app._stop_wechat_group_channel(manager)

        manager.get_channel.assert_called_once_with(const.WECHAT_GROUP)
        manager.stop.assert_called_once_with(const.WECHAT_GROUP)

    def test_cleanup_does_not_propagate_stop_failure(self):
        manager = Mock()
        manager.get_channel.return_value = object()
        manager.stop.side_effect = RuntimeError("sidecar stop failed")

        app._stop_wechat_group_channel(manager)

        manager.stop.assert_called_once_with(const.WECHAT_GROUP)

    def test_run_finally_cleans_up_wechat_group_for_all_exit_paths(self):
        exit_cases = (
            KeyboardInterrupt(),
            SystemExit(0),
            RuntimeError("main loop failed"),
        )
        for exit_error in exit_cases:
            with self.subTest(exit_type=type(exit_error).__name__):
                manager = Mock()
                cleanup = Mock()
                app._channel_mgr = None
                with patch.object(app, "load_config"), \
                        patch.object(app, "sigterm_handler_wrap"), \
                        patch.object(app, "conf", return_value={
                            "channel_type": const.WECHAT_GROUP,
                            "web_console": False,
                        }), \
                        patch.object(app, "_sync_builtin_skills"), \
                        patch.object(app, "_warmup_mcp_tools"), \
                        patch.object(app, "_warmup_scheduler"), \
                        patch.object(app, "ChannelManager", return_value=manager), \
                        patch.object(app, "_stop_wechat_group_channel", cleanup, create=True), \
                        patch.object(app.time, "sleep", side_effect=exit_error), \
                        patch.object(app.sys, "argv", ["app.py"]), \
                        patch.object(app, "DESKTOP_MODE", False), \
                        patch.object(app, "logger"):
                    if isinstance(exit_error, SystemExit):
                        with self.assertRaises(SystemExit):
                            app.run()
                    else:
                        app.run()

                manager.start.assert_called_once_with([const.WECHAT_GROUP], first_start=True)
                cleanup.assert_called_once_with(manager)


if __name__ == "__main__":
    unittest.main()
