import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class DockerDeploymentContractTest(unittest.TestCase):
    def test_dockerfile_bundles_node_and_sidecar_dependencies(self):
        text = (ROOT / "docker" / "Dockerfile.latest").read_text(encoding="utf-8")
        self.assertIn("FROM node:22-bullseye-slim AS wechat-group-sidecar-build", text)
        self.assertIn("npm ci --omit=dev", text)
        self.assertIn("npm test", text)
        self.assertIn("/usr/local/bin/node", text)
        self.assertIn("/app/channel/wechat_group/sidecar/node_modules", text)
        self.assertIn("import('wechaty')", text)
        self.assertIn("libatomic1", text)

    def test_compose_persists_private_data_and_workspace(self):
        path = ROOT / "docker" / "docker-compose.yml"
        compose = yaml.safe_load(path.read_text(encoding="utf-8"))
        service = compose["services"]["lightagent"]
        environment = service["environment"]
        self.assertEqual("/home/agent/.lightagent", environment["LIGHTAGENT_DATA_DIR"])
        self.assertEqual("0.0.0.0", environment["WEB_HOST"])
        self.assertEqual(
            "${WEB_PASSWORD:?Set WEB_PASSWORD in docker/.env before starting LightAgent}",
            environment["WEB_PASSWORD"],
        )
        self.assertNotIn("CHANNEL_TYPE", environment)
        self.assertIn("./config:/home/agent/.lightagent", service["volumes"])
        self.assertIn("./data:/home/agent/lightagent", service["volumes"])
        volume_targets = [item.rsplit(":", 1)[-1] for item in service["volumes"]]
        self.assertNotIn("/app", volume_targets)
        self.assertNotIn("version", compose)

    def test_global_template_keeps_safe_web_bind_default(self):
        template = json.loads(
            (ROOT / "config-template.json").read_text(encoding="utf-8")
        )
        self.assertEqual("", template["web_host"])

    def test_entrypoint_seeds_persistent_config_without_overwrite(self):
        text = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn(
            'LIGHTAGENT_DATA_DIR=${LIGHTAGENT_DATA_DIR:-"/home/agent/.lightagent"}',
            text,
        )
        self.assertIn('if [ ! -f "$LIGHTAGENT_DATA_DIR/config.json" ]; then', text)
        self.assertIn("config-template.json", text)

    def test_release_workflow_publishes_one_multiarch_image(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-image.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("platforms: linux/amd64,linux/arm64", workflow)
        self.assertIn("docker/setup-qemu-action", workflow)
        self.assertIn("docker/setup-buildx-action", workflow)
        self.assertFalse(
            (ROOT / ".github" / "workflows" / "deploy-image-arm.yml").exists()
        )

    def test_dockerignore_excludes_secrets_dependencies_and_runtime_data(self):
        lines = {
            line.strip()
            for line in (ROOT / ".dockerignore")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith("#")
        }
        self.assertIn("config.json", lines)
        self.assertIn(".env", lines)
        self.assertIn("docker/.env", lines)
        self.assertIn("**/node_modules/", lines)
        self.assertIn("docker/config/", lines)
        self.assertIn("docker/data/", lines)
        self.assertIn("docker/lightagent/", lines)
        self.assertIn(".worktrees/", lines)
        self.assertIn("workspace/", lines)
        self.assertIn("*.log", lines)
        self.assertIn("user_datas.pkl", lines)


if __name__ == "__main__":
    unittest.main()
