"""Regression checks for ORA8 Bootstrap empty values and public ingress guard."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bootstrap.sh"

class Ora8PostflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_full_bootstrap_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_explicit_empty_decision_model_is_preserved(self):
        self.assertIn('AI_DECISION_MODEL="\${AI_DECISION_MODEL-tev1:0.8b}"', self.source)
        self.assertNotIn('AI_DECISION_MODEL="\${AI_DECISION_MODEL:-tev1:0.8b}"', self.source)

    def test_explicit_empty_task_model_is_preserved(self):
        self.assertIn('TASK_MODEL="\${TASK_MODEL-tev1:0.8b}"', self.source)
        self.assertNotIn('TASK_MODEL="\${TASK_MODEL:-tev1:0.8b}"', self.source)

    def test_cloudflare_postflight_runs_after_local_audit(self):
        self.assertEqual(self.source.count("verify_public_panel_via_cloudflare() {"), 1)
        main = self.source[self.source.index("\nmain() {"):]
        self.assertLess(main.index("  final_audit_with_repair\n"), main.index('  CURRENT_STEP="29-public-cloudflare-reachability"'))
        self.assertLess(main.index('  CURRENT_STEP="29-public-cloudflare-reachability"'), main.index('  echo "BOOTSTRAP COMPLETE"'))

    def test_public_probe_does_not_fake_a_loopback_check(self):
        start = self.source.index("verify_public_panel_via_cloudflare() {")
        end = self.source.index("\n}\n", start)
        check = self.source[start:end]
        self.assertIn("--noproxy '*'", check)
        self.assertIn('https://\${AAPANEL_DOMAIN}/login', check)
        self.assertIn('if [[ "$proxied" != true ]]', check)

if __name__ == "__main__":
    unittest.main()
