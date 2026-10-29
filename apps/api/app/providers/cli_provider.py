"""Subscription access to frontier models through their official CLIs.

`claude -p` (Claude Code) and `codex exec` (Codex) authenticate with the
plan the operator is logged into rather than an API key, so supervisor and
reviewer calls draw on a flat-rate subscription instead of per-token spend.
The trade-off is plan rate limits - which is why the expensive, high-volume
worker tier belongs on local models and only the review tier lives here.

Hardening (these run a subprocess on the API host):
- argv lists only, never a shell; the model name is validated so it cannot
  smuggle in a flag.
- User-authored text (prompts, founder instructions) never goes in argv: the
  system prompt travels in a temp file and the user prompt on stdin. On
  Windows the npm shims are .cmd files that cmd.exe re-parses, so argv
  content there is an injection vector, not just a quoting nuisance.
- Each call runs in a fresh empty directory, so a tool-using CLI has nothing
  to read or edit.
- API keys are stripped from the child env so the CLI bills the
  subscription login, not a key that happens to be set for the API tier.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from app.config import settings
from app.providers.base import ModelResponse, ProviderError
from app.providers.openai_provider import strict_json_schema

_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\[\]/-]{0,99}$")


def validate_cli_model(model: str) -> str:
    if not _MODEL_RE.match(model):
        raise ValueError(f"invalid model name for a CLI provider: {model!r}")
    return model


def _resolve(command: str, label: str) -> str:
    path = shutil.which(command)
    if path is None:
        raise ProviderError(f"{label}: '{command}' not found on PATH")
    return path


def _is_shell_shim(path: str) -> bool:
    return path.lower().endswith((".cmd", ".bat"))


def _child_env(strip: tuple[str, ...]) -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in strip}


def _schema_in_prompt(user_prompt: str, json_schema: dict) -> str:
    return (
        f"{user_prompt}\n\nReturn ONLY a JSON object matching this JSON Schema:\n"
        f"{json.dumps(json_schema)}"
    )


def _run(argv: list[str], *, stdin: str, cwd: str, env: dict, label: str,
         timeout: int) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            argv, input=stdin, capture_output=True, text=True, encoding="utf-8",
            cwd=cwd, env=env, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProviderError(f"{label}: timed out after {timeout}s") from exc
    except OSError as exc:
        raise ProviderError(f"{label}: {type(exc).__name__}") from exc
    if proc.returncode != 0:
        # stderr can carry account details; keep only the exit code here and
        # leave diagnosis to the operator's terminal.
        raise ProviderError(f"{label}: exited with code {proc.returncode}")
    return proc


class ClaudeCodeProvider:
    """Claude via `claude -p` on the operator's Pro/Max/Team login."""

    name = "claude_code"

    def __init__(self, command: str | None = None, timeout: int | None = None):
        self._command = command or settings.claude_code_command
        self._timeout = timeout or settings.cli_timeout_seconds

    def complete(
        self, *, model: str, system_prompt: str, user_prompt: str,
        json_output: bool, max_tokens: int, json_schema: dict | None = None,
    ) -> ModelResponse:
        del max_tokens  # the CLI manages output length itself
        label = f"claude_code/{model}"
        if not settings.claude_code_enabled:
            raise ProviderError(f"{label}: disabled (set CLAUDE_CODE_ENABLED=true)")
        try:
            validate_cli_model(model)
        except ValueError as exc:
            raise ProviderError(f"{label}: invalid model name") from exc
        exe = _resolve(self._command, label)
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="verdict-cc-") as work:
            prompt_file = Path(work) / ".system-prompt.md"
            system = system_prompt
            if json_output and json_schema is None:
                system += "\n\nRespond with a single valid JSON object and nothing else."
            prompt_file.write_text(system, encoding="utf-8")
            argv = [exe, "-p", "--output-format", "json", "--model", model,
                    "--system-prompt-file", str(prompt_file)]
            stdin = user_prompt
            if json_schema is not None:
                if _is_shell_shim(exe):
                    stdin = _schema_in_prompt(user_prompt, json_schema)
                else:
                    argv += ["--json-schema", json.dumps(json_schema)]
            proc = _run(
                argv, stdin=stdin, cwd=work, label=label, timeout=self._timeout,
                env=_child_env(("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")),
            )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"{label}: non-JSON CLI output") from exc
        if data.get("is_error"):
            raise ProviderError(f"{label}: CLI reported an error ({data.get('subtype', '?')})")
        if data.get("structured_output") is not None:
            text = json.dumps(data["structured_output"])
        else:
            text = data.get("result") or ""
        usage = data.get("usage") or {}
        return ModelResponse(
            provider=self.name,
            model=model,
            text=text,
            tokens_in=(usage.get("input_tokens", 0)
                       + usage.get("cache_read_input_tokens", 0)
                       + usage.get("cache_creation_input_tokens", 0)),
            tokens_out=usage.get("output_tokens", 0),
            latency_ms=int((time.monotonic() - start) * 1000),
        )


class CodexProvider:
    """OpenAI models via `codex exec` on the operator's ChatGPT login."""

    name = "codex"

    def __init__(self, command: str | None = None, timeout: int | None = None):
        self._command = command or settings.codex_command
        self._timeout = timeout or settings.cli_timeout_seconds

    def complete(
        self, *, model: str, system_prompt: str, user_prompt: str,
        json_output: bool, max_tokens: int, json_schema: dict | None = None,
    ) -> ModelResponse:
        del max_tokens
        label = f"codex/{model}"
        if not settings.codex_enabled:
            raise ProviderError(f"{label}: disabled (set CODEX_ENABLED=true)")
        try:
            validate_cli_model(model)
        except ValueError as exc:
            raise ProviderError(f"{label}: invalid model name") from exc
        exe = _resolve(self._command, label)
        # codex exec has no system-prompt flag: both halves go on stdin.
        prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        if json_output and json_schema is None:
            prompt += "\n\nRespond with a single valid JSON object and nothing else."
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="verdict-codex-") as work:
            out_file = Path(work) / "last-message.txt"
            # exec defaults to a read-only sandbox; the empty cwd means there
            # is nothing to read either.
            argv = [exe, "exec", "--skip-git-repo-check", "-m", model,
                    "-o", str(out_file)]
            if json_schema is not None:
                schema_file = Path(work) / "schema.json"
                schema_file.write_text(json.dumps(strict_json_schema(json_schema)),
                                       encoding="utf-8")
                argv += ["--output-schema", str(schema_file)]
            argv.append("-")  # prompt from stdin
            _run(
                argv, stdin=prompt, cwd=work, label=label, timeout=self._timeout,
                env=_child_env(("OPENAI_API_KEY", "CODEX_API_KEY")),
            )
            text = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
        if not text.strip():
            raise ProviderError(f"{label}: empty final message")
        # exec reports no token usage on the final message; estimate so the
        # trace still shows volume (subscription calls are $0 either way).
        return ModelResponse(
            provider=self.name,
            model=model,
            text=text,
            tokens_in=len(prompt) // 4,
            tokens_out=len(text) // 4,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
