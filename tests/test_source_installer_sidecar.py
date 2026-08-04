import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SourceInstallerSidecarContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = (ROOT / "run.sh").read_text(encoding="utf-8")
        cls.powershell = (ROOT / "scripts" / "run.ps1").read_text(
            encoding="utf-8"
        )

    def test_bash_installs_locked_dependencies_and_checks_runtime(self):
        self.assertIn('command -v node', self.bash)
        self.assertIn('command -v npm', self.bash)
        self.assertIn('package-lock.json', self.bash)
        self.assertIn('npm ci --omit=dev', self.bash)
        self.assertNotIn('npm install --omit=dev', self.bash)
        self.assertIn('install_wechat_sidecar || return 1', self.bash)
        self.assertEqual(2, self.bash.count('if ! configure_channel; then'))

    def test_bash_supports_root_and_sudo_node_installation(self):
        self.assertIn('if [ "$(id -u)" -eq 0 ]; then', self.bash)
        self.assertIn('elif command -v sudo', self.bash)
        self.assertIn('run_wechat_sidecar_privileged apt-get install', self.bash)
        self.assertIn('run_wechat_sidecar_privileged yum install', self.bash)

    def test_powershell_installs_locked_dependencies_and_stops_on_failure(self):
        self.assertIn('Get-Command node', self.powershell)
        self.assertIn('Get-Command npm', self.powershell)
        self.assertIn('package-lock.json', self.powershell)
        self.assertIn('& npm ci --omit=dev', self.powershell)
        self.assertNotIn('& npm install --omit=dev', self.powershell)
        self.assertIn(
            'if (-not (Install-WechatSidecar)) { return $false }',
            self.powershell,
        )
        self.assertEqual(2, self.powershell.count('if (-not (Configure-Channel))'))
        self.assertGreaterEqual(self.powershell.count('exit 1'), 2)


if __name__ == "__main__":
    unittest.main()
