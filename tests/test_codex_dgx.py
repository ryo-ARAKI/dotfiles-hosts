import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CodexDgxLauncherTests(unittest.TestCase):
    def test_dgx_launcher_uses_generated_profile_and_visible_model(self) -> None:
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
        self.assertEqual(
            result.stdout.strip(),
            "abbr -a -- codex-dgx 'codex --profile ollama-launch --oss --local-provider ollama -m gpt-oss:120b'",
        )


class CodexDgxRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.home = self.temp_root / "home"
        self.bin_dir = self.temp_root / "bin"
        self.fixture_dir = self.temp_root / "fixtures"
        self.log_path = self.temp_root / "ollama.log"
        self.home.mkdir()
        self.bin_dir.mkdir()
        self.fixture_dir.mkdir()

        self.profile_fixture = self.fixture_dir / "ollama-launch.config.toml"
        self.providerless_profile_fixture = self.fixture_dir / "providerless.config.toml"
        self.catalog_fixture = self.fixture_dir / "model.json"
        catalog_path = self.home / ".codex" / "model.json"
        self.profile_fixture.write_text(
            textwrap.dedent(
                f"""\
                model = "gpt-oss:120b"
                model_provider = "ollama-launch"
                model_catalog_json = "{catalog_path}"

                [model_providers.ollama-launch]
                name = "Ollama"
                base_url = "http://127.0.0.1:11434/v1/"
                wire_api = "responses"
                """
            ),
            encoding="utf-8",
        )
        self.providerless_profile_fixture.write_text(
            textwrap.dedent(
                f"""\
                model = "gpt-oss:120b"
                model_catalog_json = "{catalog_path}"
                """
            ),
            encoding="utf-8",
        )
        self.catalog_fixture.write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "slug": "gpt-oss:120b",
                            "display_name": "gpt-oss:120b",
                            "context_window": 131072,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        self.write_executable("codex", "#!/bin/sh\nexit 0\n")
        self.write_executable(
            "ollama",
            textwrap.dedent(
                """\
                #!/bin/sh
                set -eu
                printf '%s\n' "$*" >> "$FAKE_OLLAMA_LOG"
                case "$1" in
                    show)
                        if [ "${FAKE_MODEL_MISSING:-0}" = 1 ]; then
                            exit 4
                        fi
                        [ "${2:-}" = "gpt-oss:120b" ] || exit 64
                        ;;
                    launch)
                        [ "$*" = "launch codex --config --model gpt-oss:120b --yes" ] || exit 64
                        mkdir -p "$HOME/.codex"
                        case "${FAKE_OLLAMA_MODE:-success}" in
                            success)
                                cp "$FAKE_PROFILE_SOURCE" "$HOME/.codex/ollama-launch.config.toml"
                                cp "$FAKE_CATALOG_SOURCE" "$HOME/.codex/model.json"
                                ;;
                            fail)
                                printf 'partial\n' > "$HOME/.codex/ollama-launch.config.toml"
                                printf 'partial\n' > "$HOME/.codex/model.json"
                                exit 23
                                ;;
                            malformed)
                                cp "$FAKE_PROFILE_SOURCE" "$HOME/.codex/ollama-launch.config.toml"
                                printf '{broken\n' > "$HOME/.codex/model.json"
                                ;;
                            providerless)
                                cp "$FAKE_PROVIDERLESS_PROFILE_SOURCE" "$HOME/.codex/ollama-launch.config.toml"
                                cp "$FAKE_CATALOG_SOURCE" "$HOME/.codex/model.json"
                                ;;
                            *)
                                exit 65
                                ;;
                        esac
                        ;;
                    *)
                        exit 64
                        ;;
                esac
                """
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_executable(self, name: str, content: str) -> None:
        path = self.bin_dir / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def link_system_commands(self, *names: str) -> None:
        for name in names:
            source = shutil.which(name)
            self.assertIsNotNone(source, msg=f"test prerequisite not found: {name}")
            (self.bin_dir / name).symlink_to(source)

    def run_refresh(
        self, mode: str = "success", *, model_missing: bool = False, include_system_path: bool = True
    ) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["PATH"] = f"{self.bin_dir}:/usr/bin:/bin" if include_system_path else str(self.bin_dir)
        env["FAKE_OLLAMA_LOG"] = str(self.log_path)
        env["FAKE_PROFILE_SOURCE"] = str(self.profile_fixture)
        env["FAKE_PROVIDERLESS_PROFILE_SOURCE"] = str(self.providerless_profile_fixture)
        env["FAKE_CATALOG_SOURCE"] = str(self.catalog_fixture)
        env["FAKE_OLLAMA_MODE"] = mode
        env["FAKE_MODEL_MISSING"] = "1" if model_missing else "0"
        return subprocess.run(
            ["sh", str(ROOT / "bin" / "codex-dgx-refresh")],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_refresh_generates_codex_files_with_exact_ollama_launch_command(self) -> None:
        result = self.run_refresh()

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            (self.home / ".codex" / "ollama-launch.config.toml").read_bytes(),
            self.profile_fixture.read_bytes(),
        )
        catalog = json.loads((self.home / ".codex" / "model.json").read_text(encoding="utf-8"))
        self.assertEqual([model["slug"] for model in catalog["models"]], ["gpt-oss:120b"])
        self.assertIn(
            "launch codex --config --model gpt-oss:120b --yes",
            self.log_path.read_text(encoding="utf-8").splitlines(),
        )

    def test_refresh_can_be_reexecuted(self) -> None:
        first = self.run_refresh()
        second = self.run_refresh()

        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        launch_lines = [
            line
            for line in self.log_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("launch ")
        ]
        self.assertEqual(launch_lines, ["launch codex --config --model gpt-oss:120b --yes"] * 2)

    def test_refresh_does_not_require_sha256sum(self) -> None:
        self.link_system_commands("sh", "python3", "mkdir", "mktemp", "cp", "rm", "cmp")

        result = self.run_refresh(include_system_path=False)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("updated", result.stdout)

    def test_generator_failure_restores_previous_generated_files(self) -> None:
        codex_dir = self.home / ".codex"
        profile_path = codex_dir / "ollama-launch.config.toml"
        catalog_path = codex_dir / "model.json"
        codex_dir.mkdir()
        old_profile = b'old profile\n'
        old_catalog = b'{"old": true}\n'
        profile_path.write_bytes(old_profile)
        catalog_path.write_bytes(old_catalog)

        result = self.run_refresh(mode="fail")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(profile_path.read_bytes(), old_profile)
        self.assertEqual(catalog_path.read_bytes(), old_catalog)

    def test_malformed_generated_catalog_restores_previous_generated_files(self) -> None:
        codex_dir = self.home / ".codex"
        profile_path = codex_dir / "ollama-launch.config.toml"
        catalog_path = codex_dir / "model.json"
        codex_dir.mkdir()
        old_profile = b"old profile\n"
        old_catalog = b'{"old": true}\n'
        profile_path.write_bytes(old_profile)
        catalog_path.write_bytes(old_catalog)

        result = self.run_refresh(mode="malformed")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(profile_path.read_bytes(), old_profile)
        self.assertEqual(catalog_path.read_bytes(), old_catalog)

    def test_profile_without_configured_provider_restores_previous_generated_files(self) -> None:
        codex_dir = self.home / ".codex"
        profile_path = codex_dir / "ollama-launch.config.toml"
        catalog_path = codex_dir / "model.json"
        codex_dir.mkdir()
        old_profile = b"old profile\n"
        old_catalog = b'{"old": true}\n'
        profile_path.write_bytes(old_profile)
        catalog_path.write_bytes(old_catalog)

        result = self.run_refresh(mode="providerless")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(profile_path.read_bytes(), old_profile)
        self.assertEqual(catalog_path.read_bytes(), old_catalog)

    def test_validation_failure_removes_generated_files_when_no_previous_files_exist(self) -> None:
        profile_path = self.home / ".codex" / "ollama-launch.config.toml"
        catalog_path = self.home / ".codex" / "model.json"

        for mode in ("malformed", "providerless"):
            with self.subTest(mode=mode):
                result = self.run_refresh(mode=mode)

                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(profile_path.exists())
                self.assertFalse(catalog_path.exists())

    def test_validation_failure_restores_only_previous_profile(self) -> None:
        codex_dir = self.home / ".codex"
        profile_path = codex_dir / "ollama-launch.config.toml"
        catalog_path = codex_dir / "model.json"
        codex_dir.mkdir()
        old_profile = b"old profile only\n"
        profile_path.write_bytes(old_profile)

        result = self.run_refresh(mode="malformed")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(profile_path.read_bytes(), old_profile)
        self.assertFalse(catalog_path.exists())

    def test_validation_failure_restores_only_previous_catalog(self) -> None:
        codex_dir = self.home / ".codex"
        profile_path = codex_dir / "ollama-launch.config.toml"
        catalog_path = codex_dir / "model.json"
        codex_dir.mkdir()
        old_catalog = b'{"old": "catalog only"}\n'
        catalog_path.write_bytes(old_catalog)

        result = self.run_refresh(mode="providerless")

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(profile_path.exists())
        self.assertEqual(catalog_path.read_bytes(), old_catalog)

    def test_generator_failure_removes_partial_files_when_no_previous_files_exist(self) -> None:
        profile_path = self.home / ".codex" / "ollama-launch.config.toml"
        catalog_path = self.home / ".codex" / "model.json"

        result = self.run_refresh(mode="fail")

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(profile_path.exists())
        self.assertFalse(catalog_path.exists())

    def test_missing_ollama_model_stops_before_launch(self) -> None:
        profile_path = self.home / ".codex" / "ollama-launch.config.toml"
        catalog_path = self.home / ".codex" / "model.json"

        result = self.run_refresh(model_missing=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ollama model is not installed: gpt-oss:120b", result.stderr)
        self.assertNotIn(
            "launch codex --config --model gpt-oss:120b --yes",
            self.log_path.read_text(encoding="utf-8").splitlines(),
        )
        self.assertFalse(profile_path.exists())
        self.assertFalse(catalog_path.exists())

    def test_refresh_reports_updated_then_unchanged(self) -> None:
        first = self.run_refresh()
        second = self.run_refresh()

        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        self.assertIn("updated", first.stdout)
        self.assertIn("unchanged", second.stdout)


if __name__ == "__main__":
    unittest.main()
