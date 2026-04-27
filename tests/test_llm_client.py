import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm_client import LLMClient, _coerce_anthropic_content, call_llm, require_llm_ready


class LLMClientTests(unittest.TestCase):
    def test_codex_provider_uses_stdout_file_and_stdin_prompt(self):
        calls = []

        def fake_run(cmd, input=None, text=None, capture_output=None, timeout=None, cwd=None, check=None):
            calls.append({
                "cmd": cmd,
                "input": input,
                "text": text,
                "capture_output": capture_output,
                "timeout": timeout,
                "cwd": cwd,
                "check": check,
            })
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.write_text("CODEX RESULT")

            class Result:
                returncode = 0
                stdout = "noisy cli logs"
                stderr = ""

            return Result()

        client = LLMClient(provider="codex", codex_command="codex", codex_sandbox="read-only")
        with patch("llm_client.subprocess.run", fake_run):
            result = client.complete(
                "Write the scene.",
                system="You are a novelist.",
                max_tokens=1234,
                temperature=0.7,
                role="writer",
                timeout=42,
            )

        self.assertEqual(result, "CODEX RESULT")
        self.assertEqual(len(calls), 1)
        cmd = calls[0]["cmd"]
        self.assertEqual(cmd[:4], ["codex", "exec", "--sandbox", "read-only"])
        self.assertIn("-o", cmd)
        self.assertEqual(cmd[-1], "-")
        self.assertIn("SYSTEM INSTRUCTIONS:\nYou are a novelist.", calls[0]["input"])
        self.assertIn("USER PROMPT:\nWrite the scene.", calls[0]["input"])
        self.assertEqual(calls[0]["timeout"], 42)

    def test_codex_provider_can_use_shell_like_command_string(self):
        seen = {}

        def fake_run(cmd, input=None, text=None, capture_output=None, timeout=None, cwd=None, check=None):
            seen["cmd"] = cmd
            Path(cmd[cmd.index("-o") + 1]).write_text("OK")

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        client = LLMClient(provider="codex", codex_command="npx -y @openai/codex@latest")
        with patch("llm_client.subprocess.run", fake_run):
            self.assertEqual(client.complete("hi"), "OK")

        self.assertEqual(seen["cmd"][:4], ["npx", "-y", "@openai/codex@latest", "exec"])

    def test_codex_provider_ignores_anthropic_model_names_passed_by_scripts(self):
        seen = {}

        def fake_run(cmd, input=None, text=None, capture_output=None, timeout=None, cwd=None, check=None):
            seen["cmd"] = cmd
            Path(cmd[cmd.index("-o") + 1]).write_text("OK")

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        client = LLMClient(provider="codex", codex_command="codex", codex_model="")
        with patch("llm_client.subprocess.run", fake_run):
            self.assertEqual(client.complete("hi", model="claude-sonnet-4-6-20250217"), "OK")

        self.assertNotIn("--model", seen["cmd"])

    def test_codex_provider_falls_back_to_stdout_when_output_file_empty(self):
        def fake_run(cmd, input=None, text=None, capture_output=None, timeout=None, cwd=None, check=None):
            class Result:
                returncode = 0
                stdout = "Codex logs\nFINAL ANSWER\n"
                stderr = ""

            return Result()

        client = LLMClient(provider="codex", codex_command="codex")
        with patch("llm_client.subprocess.run", fake_run):
            self.assertEqual(client.complete("hi"), "Codex logs\nFINAL ANSWER")

    def test_codex_provider_raises_helpful_error_on_nonzero_exit(self):
        def fake_run(cmd, input=None, text=None, capture_output=None, timeout=None, cwd=None, check=None):
            class Result:
                returncode = 1
                stdout = "out"
                stderr = "bad model"

            return Result()

        client = LLMClient(provider="codex", codex_command="codex")
        with patch("llm_client.subprocess.run", fake_run):
            with self.assertRaisesRegex(RuntimeError, "Codex CLI failed"):
                client.complete("hi")

    def test_anthropic_content_parser_accepts_text_blocks(self):
        payload = {"content": [{"type": "text", "text": "hello"}, {"type": "tool_use", "name": "x"}]}
        self.assertEqual(_coerce_anthropic_content(payload), "hello")

    def test_call_llm_reads_provider_from_environment(self):
        with patch.dict(os.environ, {"AUTONOVEL_LLM_PROVIDER": "codex", "AUTONOVEL_CODEX_COMMAND": "codex"}, clear=False):
            with patch.object(LLMClient, "complete", return_value="ENV OK") as complete:
                self.assertEqual(call_llm("prompt", role="judge"), "ENV OK")
                self.assertEqual(complete.call_args.kwargs["role"], "judge")

    def test_require_llm_ready_allows_codex_without_anthropic_key(self):
        with patch.dict(os.environ, {"AUTONOVEL_LLM_PROVIDER": "codex"}, clear=True):
            require_llm_ready(role="writer")

    def test_require_llm_ready_requires_key_for_anthropic(self):
        with patch.dict(os.environ, {"AUTONOVEL_LLM_PROVIDER": "anthropic"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_API_KEY"):
                require_llm_ready(role="writer")

    def test_python_scripts_route_anthropic_messages_through_adapter(self):
        root = Path(__file__).resolve().parents[1]
        offenders = []
        for path in root.glob("*.py"):
            if path.name == "llm_client.py":
                continue
            if "/v1/messages" in path.read_text():
                offenders.append(path.name)

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
