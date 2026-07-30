# encoding:utf-8
import unittest

from agent.skills.formatter import format_unavailable_skills_for_prompt
from agent.skills.types import Skill, SkillEntry


class SkillFormatterTest(unittest.TestCase):
    def test_unavailable_skill_prompt_requires_final_facing_language(self):
        skill = Skill(
            name="image-generation",
            description="Generate images",
            file_path="skills/image-generation/SKILL.md",
            base_dir="skills/image-generation",
            source="builtin",
            content=(
                "# Image Generation\n\n"
                "## Setup\n"
                "Configure one supported image provider.\n"
            ),
        )

        prompt = format_unavailable_skills_for_prompt(
            [SkillEntry(skill=skill)],
            {"image-generation": {"anyEnv": ["OPENAI_API_KEY", "GEMINI_API_KEY"]}},
        )

        self.assertIn("final-facing capability response", prompt)
        self.assertIn("Do not narrate checks, routing, or private deliberation", prompt)
        self.assertIn("Only state requirements present in <missing>", prompt)
        self.assertNotIn("Guide the user to complete the setup", prompt)


if __name__ == "__main__":
    unittest.main()
