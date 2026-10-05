import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CodexDgxLauncherTests(unittest.TestCase):
    def test_dgx_launcher_uses_explicit_managed_profiles(self) -> None:
        launcher = ROOT / "config" / "fish" / "conf.d" / "95-codex-dgx.fish"

        result = subprocess.run(
            [
                "fish",
                "--no-config",
                "-ic",
                f'source "{launcher}"; abbr --show | string match -- "*codex-dgx*"',
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        for name, profile in (
            ("codex-dgx", "ollama-coding"),
            ("codex-dgx-code", "ollama-coding"),
            ("codex-dgx-research", "ollama-research"),
            ("codex-dgx-fast", "ollama-fast"),
        ):
            with self.subTest(abbreviation=name):
                self.assertIn(f"abbr -a -- {name} 'codex --profile {profile} -C .'", result.stdout)
        self.assertNotIn("--oss", result.stdout)
        self.assertNotIn("ollama-launch", result.stdout)

    def test_dgx_manifest_cannot_reinstall_legacy_refresh(self) -> None:
        rows = (ROOT / "manifest/dgx.tsv").read_text().splitlines()
        targets = {row.split("\t")[1] for row in rows if row.strip()}
        self.assertNotIn("~/.local/bin/codex-dgx-refresh", targets)


if __name__ == "__main__":
    unittest.main()
