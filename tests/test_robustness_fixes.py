# encoding:utf-8
"""
Unit tests for robustness fixes:
  1. ChatChannel.cancel_session / cancel_all_session must not raise KeyError
     when a session has been produced but no task has been dispatched yet
     (so self.futures[session_id] does not exist).
  2. common.utils.compress_imgfile must terminate (no infinite loop / invalid
     PIL quality) when an image cannot be compressed below max_size.
"""
import io
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# =============================================================================
# 0. Context kwargs isolation regression
# =============================================================================

class TestContextKwargsIsolation(unittest.TestCase):
    """Context instances must not share kwargs through a mutable default."""

    def test_context_kwargs_are_not_shared_between_instances(self):
        from bridge.context import Context, ContextType

        first = Context(ContextType.TEXT, "scheduled")
        first["is_scheduled_task"] = True

        second = Context(ContextType.TEXT, "normal")
        second["session_id"] = "sid"

        self.assertIsNone(second.get("is_scheduled_task"))
        self.assertNotIn("session_id", first)


# =============================================================================
# 1. cancel_session / cancel_all_session KeyError regression
# =============================================================================

class TestCancelSessionMissingFutures(unittest.TestCase):
    """A session may exist in self.sessions before any future is recorded."""

    def _make_channel(self):
        # Import lazily and build a bare object without running __init__,
        # to avoid pulling the full channel setup / config.
        from channel.chat_channel import ChatChannel

        ch = ChatChannel.__new__(ChatChannel)
        import threading

        ch.lock = threading.RLock()
        # A produced session whose future has NOT been dispatched yet.
        queue = MagicMock()
        queue.qsize.return_value = 0
        semaphore = MagicMock()
        ch.sessions = {"sid": [queue, semaphore]}
        ch.futures = {}  # intentionally empty: consume() never ran
        return ch

    def test_cancel_session_no_futures_entry(self):
        ch = self._make_channel()
        # Should not raise KeyError.
        try:
            ch.cancel_session("sid")
        except KeyError:
            self.fail("cancel_session raised KeyError when futures entry missing")

    def test_cancel_all_session_no_futures_entry(self):
        ch = self._make_channel()
        try:
            ch.cancel_all_session()
        except KeyError:
            self.fail("cancel_all_session raised KeyError when futures entry missing")

    def test_cancel_session_cancels_existing_futures(self):
        ch = self._make_channel()
        fut = MagicMock()
        ch.futures["sid"] = [fut]
        ch.cancel_session("sid")
        fut.cancel.assert_called_once()


class TestChatChannelConsumeRobustness(unittest.TestCase):
    """consume() must keep later sessions visible after one session fails."""

    class _StopConsume(BaseException):
        pass

    class _SessionsWithBrokenSnapshot(dict):
        def __init__(self, alive_value):
            super().__init__({"alive": alive_value})

        def keys(self):
            return ["missing", "broken", "alive"]

        def __getitem__(self, key):
            if key == "missing":
                raise KeyError(key)
            if key == "broken":
                return ["not-a-session-state"]
            return super().__getitem__(key)

    class _Future:
        def __init__(self):
            self.callbacks = []

        def add_done_callback(self, callback):
            self.callbacks.append(callback)

        def done(self):
            return False

    class _CallbackFailFuture:
        def add_done_callback(self, callback):
            raise RuntimeError("callback registration failed")

    class _HandlerPool:
        def __init__(self, future=None):
            self.submitted = []
            self.future = future

        def submit(self, func, context):
            self.submitted.append((func, context))
            return self.future or TestChatChannelConsumeRobustness._Future()

    def _make_channel(self, sessions):
        from channel.chat_channel import ChatChannel
        import threading

        ch = ChatChannel.__new__(ChatChannel)
        ch.lock = threading.RLock()
        ch.sessions = sessions
        ch.futures = {}
        return ch

    def test_consume_skips_missing_or_broken_snapshot_session_and_dispatches_later_session(self):
        from bridge.context import Context, ContextType
        import channel.chat_channel as chat_channel

        context = Context(ContextType.IMAGE_CREATE, "a cat")
        context["session_id"] = "alive"
        queue = MagicMock()
        queue.empty.return_value = False
        queue.get.return_value = context
        semaphore = MagicMock()
        semaphore.acquire.return_value = True
        sessions = self._SessionsWithBrokenSnapshot([queue, semaphore])
        ch = self._make_channel(sessions)
        handler_pool = self._HandlerPool()

        with patch.object(chat_channel, "handler_pool", handler_pool), \
                patch.object(chat_channel.time, "sleep", side_effect=self._StopConsume), \
                self.assertLogs("log", level="INFO") as captured:
            with self.assertRaises(self._StopConsume):
                ch.consume()

        self.assertEqual([(ch._handle, context)], handler_pool.submitted)
        self.assertIn("[chat_channel] image-create dispatching", "\n".join(captured.output))

    def test_consume_keeps_session_with_pending_future_without_assert_loop(self):
        import channel.chat_channel as chat_channel

        queue = MagicMock()
        queue.empty.return_value = True
        semaphore = MagicMock()
        semaphore.acquire.return_value = True
        semaphore._initial_value = 1
        semaphore._value = 0
        sessions = {"sid": [queue, semaphore]}
        ch = self._make_channel(sessions)
        ch.futures["sid"] = [self._Future()]

        with patch.object(chat_channel.time, "sleep", side_effect=self._StopConsume), \
                self.assertLogs("log", level="WARNING") as captured:
            with self.assertRaises(self._StopConsume):
                ch.consume()

        self.assertIn("consume keep session with pending futures", "\n".join(captured.output))
        self.assertIn("sid", ch.sessions)
        semaphore.release.assert_called_once()

    def test_consume_releases_semaphore_when_callback_registration_fails(self):
        from bridge.context import Context, ContextType
        import channel.chat_channel as chat_channel

        context = Context(ContextType.TEXT, "hello")
        context["session_id"] = "sid"
        queue = MagicMock()
        queue.empty.return_value = False
        queue.get.return_value = context
        semaphore = MagicMock()
        semaphore.acquire.return_value = True
        sessions = {"sid": [queue, semaphore]}
        ch = self._make_channel(sessions)
        handler_pool = self._HandlerPool(future=self._CallbackFailFuture())

        with patch.object(chat_channel, "handler_pool", handler_pool), \
                patch.object(chat_channel.time, "sleep", side_effect=self._StopConsume), \
                self.assertLogs("log", level="ERROR"):
            with self.assertRaises(self._StopConsume):
                ch.consume()

        semaphore.release.assert_called_once()


class TestChatChannelImageCreateLogging(unittest.TestCase):
    """Image-create contexts need searchable async-pipeline logs."""

    def _make_channel(self):
        from channel.chat_channel import ChatChannel
        import threading

        ch = ChatChannel.__new__(ChatChannel)
        ch.lock = threading.RLock()
        ch.sessions = {}
        ch.futures = {}
        return ch

    def test_produce_logs_image_create_enqueue(self):
        from bridge.context import Context, ContextType

        ch = self._make_channel()
        context = Context(ContextType.IMAGE_CREATE, "a cat")
        context["session_id"] = "sid"

        with self.assertLogs("log", level="INFO") as captured:
            ch.produce(context)

        self.assertIn("[chat_channel] image-create enqueued", "\n".join(captured.output))

    def test_handle_logs_image_create_processing(self):
        from bridge.context import Context, ContextType

        ch = self._make_channel()
        ch._generate_reply = MagicMock(return_value=None)
        context = Context(ContextType.IMAGE_CREATE, "a cat")

        with self.assertLogs("log", level="INFO") as captured:
            ch._handle(context)

        self.assertIn("[chat_channel] image-create handling", "\n".join(captured.output))


# =============================================================================
# 2. compress_imgfile termination
# =============================================================================

class TestCompressImgfileTermination(unittest.TestCase):
    """compress_imgfile must always return, even for incompressible input."""

    def setUp(self):
        # Skip if Pillow is not available in the test environment.
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("Pillow not installed")

    def _make_image_buf(self, size=(64, 64)):
        from PIL import Image
        import random

        img = Image.new("RGB", size)
        # Fill with random noise so JPEG cannot compress it well.
        pixels = [
            (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            for _ in range(size[0] * size[1])
        ]
        img.putdata(pixels)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=95)
        buf.seek(0)
        return buf

    def test_returns_when_target_unreachable(self):
        from common.utils import compress_imgfile

        buf = self._make_image_buf()
        # An impossibly small target that even quality=10 won't reach.
        out = compress_imgfile(buf, max_size=10)
        self.assertIsInstance(out, io.BytesIO)
        # Verify the result is still a valid JPEG (PIL never got invalid quality).
        from PIL import Image

        out.seek(0)
        img = Image.open(out)
        img.verify()

    def test_no_compression_needed_returns_same_object(self):
        from common.utils import compress_imgfile

        buf = self._make_image_buf()
        size = buf.getbuffer().nbytes
        out = compress_imgfile(buf, max_size=size + 1)
        self.assertIs(out, buf)


if __name__ == "__main__":
    unittest.main()
