from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
_MAX_TOKENS = 250
_MAX_HISTORY = 5  # turns per user (1 turn = user + assistant pair)

# Lazy-import openai so the bot starts fine even without the package
_openai = None


def _get_openai():
    global _openai
    if _openai is None:
        import openai as _oi
        _oi.api_key = _OPENAI_API_KEY
        _openai = _oi
    return _openai


def is_available() -> bool:
    return bool(_OPENAI_API_KEY)


# In-memory per-user conversation history: user_id -> list of {role, content}
_histories: dict[int | str, list[dict]] = {}


class AIService:
    """
    Wraps OpenAI chat completions for two modes:
    - NLU mode: tries to map user intent to a registered command
    - Chat mode: direct conversational response
    """

    def __init__(self, command_registry: dict[str, str] | None = None) -> None:
        """
        command_registry: {path: description} for all registered commands.
        Pass None to run in pure-chat mode.
        """
        self._registry = command_registry or {}

    def _system_prompt(self, nlu: bool) -> str:
        if nlu and self._registry:
            cmd_list = "\n".join(
                f"  {path}: {desc}" for path, desc in sorted(self._registry.items())
            )
            return (
                "You are an SMS assistant that controls a home automation system.\n"
                "Available commands (path: description):\n"
                f"{cmd_list}\n\n"
                "When the user's message clearly matches one of the above commands, respond ONLY with "
                "valid JSON (no markdown) in this exact format:\n"
                '{"type":"command","path":"<path>","args":["<arg1>","<arg2>"]}\n'
                "where args are the positional arguments the command expects.\n"
                "IMPORTANT: For duration arguments (e.g. '10 min', '2 hours', '30 seconds'), "
                "always keep the number and unit together as a single arg string (e.g. '10 min', not '10' and 'min').\n"
                "If the message does NOT match any command, respond ONLY with:\n"
                '{"type":"chat","message":"<your response>"}\n'
                "Keep chat responses brief (under 200 characters)."
            )
        return (
            "You are a concise SMS assistant. Keep responses under 200 characters. "
            "Be direct and helpful."
        )

    def _trim_history(self, user_key: int | str) -> None:
        history = _histories.get(user_key, [])
        # Each turn is 2 messages (user + assistant); keep last _MAX_HISTORY turns
        max_msgs = _MAX_HISTORY * 2
        if len(history) > max_msgs:
            _histories[user_key] = history[-max_msgs:]

    def chat(self, message: str, user_key: int | str, nlu: bool = False) -> dict:
        """
        Returns:
          {"type": "command", "path": str, "args": list[str]}  — if NLU found a match
          {"type": "chat", "message": str}                      — conversational reply
          {"type": "error", "message": str}                     — on failure
        """
        if not is_available():
            return {"type": "error", "message": "AI is not configured (missing OPENAI_API_KEY)"}

        oi = _get_openai()
        history = _histories.setdefault(user_key, [])
        history.append({"role": "user", "content": message})
        self._trim_history(user_key)

        messages = [{"role": "system", "content": self._system_prompt(nlu)}] + history

        try:
            resp = oi.chat.completions.create(
                model=_MODEL,
                messages=messages,
                max_tokens=_MAX_TOKENS,
                temperature=0.4,
            )
            raw = resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
            history.pop()  # Remove the user message we added
            return {"type": "error", "message": "AI service unavailable"}

        # Record assistant reply in history
        history.append({"role": "assistant", "content": raw})
        self._trim_history(user_key)

        if nlu:
            try:
                parsed = json.loads(raw)
                if parsed.get("type") in ("command", "chat"):
                    return parsed
            except (json.JSONDecodeError, AttributeError):
                pass
            # If JSON parse failed, treat as plain chat response
            return {"type": "chat", "message": raw}

        return {"type": "chat", "message": raw}
