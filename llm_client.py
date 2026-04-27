#!/usr/bin/env python3
"""Shared LLM adapter for autonovel.

Default provider remains Anthropic for upstream compatibility. Set
AUTONOVEL_LLM_PROVIDER=codex to run generation/evaluation through the Codex CLI
using the local ChatGPT/Codex auth session instead of an Anthropic API key.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_ANTHROPIC_MODELS = {
    "writer": "claude-sonnet-4-6",
    "judge": "claude-opus-4-6",
    "review": "claude-opus-4-6",
}

ROLE_MODEL_ENV = {
    "writer": "AUTONOVEL_WRITER_MODEL",
    "judge": "AUTONOVEL_JUDGE_MODEL",
    "review": "AUTONOVEL_REVIEW_MODEL",
}


@dataclass
class LLMClient:
    provider: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    anthropic_beta: str | None = None
    codex_command: str | None = None
    codex_model: str | None = None
    codex_sandbox: str | None = None
    cwd: str | Path | None = None

    def __post_init__(self) -> None:
        self.provider = (self.provider or os.environ.get("AUTONOVEL_LLM_PROVIDER", "anthropic")).lower()
        self.anthropic_api_key = self.anthropic_api_key if self.anthropic_api_key is not None else os.environ.get("ANTHROPIC_API_KEY", "")
        self.anthropic_base_url = self.anthropic_base_url or os.environ.get("AUTONOVEL_API_BASE_URL", "https://api.anthropic.com")
        self.anthropic_beta = self.anthropic_beta if self.anthropic_beta is not None else os.environ.get("AUTONOVEL_ANTHROPIC_BETA", "context-1m-2025-08-07")
        self.codex_command = self.codex_command or os.environ.get("AUTONOVEL_CODEX_COMMAND", "npx -y @openai/codex@latest")
        self.codex_model = self.codex_model if self.codex_model is not None else os.environ.get("AUTONOVEL_CODEX_MODEL", "")
        self.codex_sandbox = self.codex_sandbox or os.environ.get("AUTONOVEL_CODEX_SANDBOX", "read-only")
        self.cwd = Path(self.cwd or os.environ.get("AUTONOVEL_CODEX_CWD", BASE_DIR))

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        role: str = "writer",
        model: str | None = None,
        timeout: int | None = None,
    ) -> str:
        if self.provider == "anthropic":
            return self._complete_anthropic(prompt, system=system, max_tokens=max_tokens, temperature=temperature, role=role, model=model, timeout=timeout)
        if self.provider == "codex":
            return self._complete_codex(prompt, system=system, max_tokens=max_tokens, temperature=temperature, role=role, model=model, timeout=timeout)
        raise ValueError(f"Unsupported AUTONOVEL_LLM_PROVIDER={self.provider!r}; expected 'anthropic' or 'codex'")

    def _resolve_anthropic_model(self, role: str, model: str | None) -> str:
        if model:
            return model
        env_name = ROLE_MODEL_ENV.get(role, "AUTONOVEL_WRITER_MODEL")
        return os.environ.get(env_name, DEFAULT_ANTHROPIC_MODELS.get(role, DEFAULT_ANTHROPIC_MODELS["writer"]))

    def _complete_anthropic(
        self,
        prompt: str,
        *,
        system: str | None,
        max_tokens: int,
        temperature: float,
        role: str,
        model: str | None,
        timeout: int | None,
    ) -> str:
        if not self.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when AUTONOVEL_LLM_PROVIDER=anthropic. Set AUTONOVEL_LLM_PROVIDER=codex to use Codex instead.")

        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if self.anthropic_beta:
            headers["anthropic-beta"] = self.anthropic_beta

        payload: dict[str, Any] = {
            "model": self._resolve_anthropic_model(role, model),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        resp = httpx.post(
            f"{self.anthropic_base_url}/v1/messages",
            headers=headers,
            json=payload,
            timeout=timeout or int(os.environ.get("AUTONOVEL_HTTP_TIMEOUT", "600")),
        )
        resp.raise_for_status()
        return _coerce_anthropic_content(resp.json())

    def _complete_codex(
        self,
        prompt: str,
        *,
        system: str | None,
        max_tokens: int,
        temperature: float,
        role: str,
        model: str | None,
        timeout: int | None,
    ) -> str:
        # Codex CLI does not expose Anthropic-style max_tokens/temperature knobs.
        # Preserve them in the prompt so the agent can honor the intent.
        composed_prompt = _compose_codex_prompt(
            prompt,
            system=system,
            role=role,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        with tempfile.NamedTemporaryFile(prefix="autonovel-codex-", suffix=".txt", delete=False) as f:
            output_path = Path(f.name)

        cmd = shlex.split(self.codex_command) + ["exec", "--sandbox", self.codex_sandbox]
        # The scripts pass their Anthropic model env vars through `model` for
        # backwards compatibility. When running through Codex, only the Codex-
        # specific env/config should select a CLI model; otherwise let Codex use
        # the user's configured default.
        selected_model = self.codex_model
        if selected_model:
            cmd += ["--model", selected_model]
        cmd += ["-o", str(output_path), "-"]

        try:
            result = subprocess.run(
                cmd,
                input=composed_prompt,
                text=True,
                capture_output=True,
                timeout=timeout or int(os.environ.get("AUTONOVEL_CODEX_TIMEOUT", "1800")),
                cwd=str(self.cwd),
                check=False,
            )
            output = output_path.read_text().strip() if output_path.exists() else ""
        finally:
            try:
                output_path.unlink()
            except FileNotFoundError:
                pass

        if result.returncode != 0:
            tail = "\n".join((result.stderr or result.stdout or "").splitlines()[-20:])
            raise RuntimeError(f"Codex CLI failed with exit code {result.returncode}:\n{tail}")

        return output or (result.stdout or "").strip()


def _compose_codex_prompt(
    prompt: str,
    *,
    system: str | None,
    role: str,
    max_tokens: int,
    temperature: float,
) -> str:
    parts = [
        "You are running as the model backend for the autonovel pipeline.",
        f"ROLE: {role}",
        f"TARGET_MAX_TOKENS: {max_tokens}",
        f"CREATIVE_TEMPERATURE_HINT: {temperature}",
        "Return only the requested artifact/content. Do not mention Codex, tools, files, or this wrapper unless explicitly asked.",
    ]
    if system:
        parts.extend(["", "SYSTEM INSTRUCTIONS:", system])
    parts.extend(["", "USER PROMPT:", prompt])
    return "\n".join(parts)


def _coerce_anthropic_content(payload: dict[str, Any]) -> str:
    content = payload.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text", "")))
            elif isinstance(block, dict) and "text" in block:
                texts.append(str(block["text"]))
        return "\n".join(t for t in texts if t)
    return json.dumps(content)


def call_llm(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.7,
    role: str = "writer",
    model: str | None = None,
    timeout: int | None = None,
) -> str:
    return LLMClient().complete(
        prompt,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
        role=role,
        model=model,
        timeout=timeout,
    )


def require_llm_ready(role: str = "writer") -> None:
    provider = os.environ.get("AUTONOVEL_LLM_PROVIDER", "anthropic").lower()
    if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic. Set AUTONOVEL_LLM_PROVIDER=codex to use Codex instead.")
    if provider == "codex":
        return
    if provider not in {"anthropic", "codex"}:
        raise RuntimeError(f"Unsupported AUTONOVEL_LLM_PROVIDER={provider!r}")
