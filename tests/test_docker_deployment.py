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
        self.assertIn("python3 make g++", text)
        self.assertLess(text.index("python3 make g++"), text.index("npm ci --omit=dev"))
        self.assertIn("/usr/local/bin/node", text)
        self.assertIn("/app/channel/wechat_group/sidecar/node_modules", text)
        self.assertIn("import('wechaty')", text)
        self.assertIn("libatomic1", text)

    def test_apt_downloads_have_bounded_retries_in_every_stage(self):
        text = (ROOT / "docker" / "Dockerfile.latest").read_text(encoding="utf-8")
        apt_stages = [stage for stage in text.split("\nFROM ") if "apt-get" in stage]

        self.assertGreaterEqual(len(apt_stages), 2)
        for stage in apt_stages:
            with self.subTest(stage=stage.splitlines()[0]):
                self.assertIn('Acquire::Retries "3";', stage)

    def test_dockerfile_caches_stable_dependencies_before_application_sources(self):
        text = (ROOT / "docker" / "Dockerfile.latest").read_text(encoding="utf-8")
        source_copy = "COPY --chown=agent:agent . ${BUILD_PREFIX}"
        stable_runtime_copies = (
            "COPY --from=wechat-group-sidecar-build /usr/local/bin/node /usr/local/bin/node",
            "COPY --from=wechat-group-sidecar-build /usr/local/bin/npm /usr/local/bin/npm",
            "COPY --from=wechat-group-sidecar-build /usr/local/bin/npx /usr/local/bin/npx",
            "COPY --from=wechat-group-sidecar-build /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm",
            "COPY --from=wechat-group-sidecar-build --chown=agent:agent",
        )

        self.assertIn("ARG INSTALL_BROWSER=true", text)
        self.assertLess(
            text.index("COPY requirements.txt /tmp/lightagent-requirements/requirements.txt"),
            text.index(source_copy),
        )
        self.assertLess(
            text.index("pip install --no-cache -r /tmp/lightagent-requirements/requirements.txt"),
            text.index(source_copy),
        )
        self.assertLess(text.index("python -m playwright install chromium"), text.index(source_copy))
        for copy_instruction in stable_runtime_copies:
            with self.subTest(copy_instruction=copy_instruction):
                self.assertLess(text.index(copy_instruction), text.index(source_copy))
        self.assertLess(text.index("wechat-group-sidecar imports ok"), text.index(source_copy))
        self.assertLess(text.index(source_copy), text.index("pip install --no-cache --no-deps -e ."))

    def test_compose_persists_private_data_and_workspace(self):
        path = ROOT / "docker" / "docker-compose.yml"
        compose = yaml.safe_load(path.read_text(encoding="utf-8"))
        service = compose["services"]["lightagent"]
        environment = service["environment"]
        self.assertEqual("/home/agent/.lightagent", environment["LIGHTAGENT_DATA_DIR"])
        self.assertEqual(
            "/home/agent/lightagent/images",
            environment["IMAGE_OUTPUT_DIR"],
        )
        self.assertEqual("0.0.0.0", environment["WEB_HOST"])
        self.assertEqual(
            "${WEB_PASSWORD:-__LIGHTAGENT_AUTO_GENERATE__}",
            environment["WEB_PASSWORD"],
        )
        self.assertNotIn("CHANNEL_TYPE", environment)
        self.assertIn("./config:/home/agent/.lightagent", service["volumes"])
        self.assertIn("./data:/home/agent/lightagent", service["volumes"])
        self.assertTrue(
            environment["IMAGE_OUTPUT_DIR"].startswith("/home/agent/lightagent/")
        )
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
        self.assertIn(
            'IMAGE_OUTPUT_DIR=${IMAGE_OUTPUT_DIR:-"/home/agent/lightagent/images"}',
            text,
        )
        self.assertIn(
            'mkdir -p "$LIGHTAGENT_DATA_DIR" /home/agent/lightagent "$IMAGE_OUTPUT_DIR"',
            text,
        )
        self.assertIn('if [ ! -f "$LIGHTAGENT_DATA_DIR/config.json" ]; then', text)
        self.assertIn("config-template.json", text)
        self.assertIn("__LIGHTAGENT_AUTO_GENERATE__", text)
        self.assertIn("secrets.token_urlsafe", text)
        self.assertIn("unset WEB_PASSWORD", text)
        self.assertIn(
            'echo "[LightAgent] Web console password: $managed_password"',
            text,
        )
        self.assertIn('"$IMAGE_OUTPUT_DIR"', text)
        self.assertIn("Password is persisted in", text)

    def test_release_workflow_builds_on_native_runners_and_merges_manifests(self):
        workflow_path = ROOT / ".github" / "workflows" / "deploy-image.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(workflow)
        build_job = parsed["jobs"]["build-and-push-image"]
        manifest_job = parsed["jobs"]["publish-manifest"]
        cleanup_job = parsed["jobs"]["cleanup-ghcr"]
        matrix = build_job["strategy"]["matrix"]["include"]
        platform_runners = {
            (entry["variant"], entry["platform"]): entry["runner"]
            for entry in matrix
        }

        self.assertEqual(
            {
                ("base", "linux/amd64"): "ubuntu-24.04",
                ("base", "linux/arm64"): "ubuntu-24.04-arm",
                ("skills-full", "linux/amd64"): "ubuntu-24.04",
                ("skills-full", "linux/arm64"): "ubuntu-24.04-arm",
            },
            platform_runners,
        )
        build_step = next(
            step
            for step in build_job["steps"]
            if step.get("uses") == "docker/build-push-action@v6"
        )
        self.assertEqual("${{ matrix.platform }}", build_step["with"]["platforms"])
        self.assertIn("push-by-digest=true", build_step["with"]["outputs"])
        self.assertIn("name-canonical=true", build_step["with"]["outputs"])
        self.assertEqual(
            "type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache-${{ matrix.variant }}-${{ matrix.arch }}",
            build_step["with"]["cache-from"],
        )
        self.assertEqual(
            "type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache-${{ matrix.variant }}-${{ matrix.arch }},mode=max",
            build_step["with"]["cache-to"],
        )
        self.assertNotIn("docker/setup-qemu-action", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("actions/download-artifact@v4", workflow)
        self.assertIn("docker buildx imagetools create", workflow)
        self.assertEqual("build-and-push-image", manifest_job["needs"])
        self.assertNotIn(
            "actions/delete-package-versions@v4",
            [step.get("uses") for step in manifest_job["steps"]],
        )
        self.assertEqual("publish-manifest", cleanup_job["needs"])
        self.assertIn(
            "needs.publish-manifest.result == 'success'",
            cleanup_job["if"],
        )
        self.assertIn(
            "actions/delete-package-versions@v4",
            [step.get("uses") for step in cleanup_job["steps"]],
        )
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
        self.assertIn(".github/", lines)
        self.assertIn(".playwright-mcp/", lines)
        self.assertIn("desktop/", lines)
        self.assertIn("docs/", lines)
        self.assertIn("plans/", lines)
        self.assertIn("tests/", lines)
        self.assertIn("workspace/", lines)
        self.assertIn("*.log", lines)
        self.assertIn("nohup.out", lines)
        self.assertIn("*.pid", lines)
        self.assertIn("user_datas.pkl", lines)
        self.assertIn("AGENTS.md", lines)
        self.assertIn("CHANGES.md", lines)
        self.assertIn("SERVER_ACCESS.md", lines)


if __name__ == "__main__":
    unittest.main()
