# encoding:utf-8
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class SchedulerToolStub:
    name = "scheduler"


class TestPromptSchedulerGuidance(unittest.TestCase):
    def test_tooling_section_requires_scheduler_tool_for_scheduled_requests(self):
        from agent.prompt.builder import _build_tooling_section

        prompt = "\n".join(_build_tooling_section([SchedulerToolStub()], "en"))

        self.assertIn("scheduled tasks", prompt)
        self.assertIn("must call `scheduler`", prompt)
        self.assertIn("Do not verbally confirm", prompt)


if __name__ == "__main__":
    unittest.main()
