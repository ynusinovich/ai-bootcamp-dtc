from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Any

import pydantic
from pydantic import BaseModel

from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.run import AgentRunResult
from pydantic_ai.result import StreamedRunResult

UsageTypeAdapter = pydantic.TypeAdapter(RunUsage)


def create_log_entry(
    agent: Agent,
    messages: List[ModelMessage],
    usage: RunUsage,
    output: Any,  # WikiAnswer or str
) -> dict:
    tools: list[str] = []
    for ts in agent.toolsets:
        tools.extend(ts.tools.keys())

    dict_messages = ModelMessagesTypeAdapter.dump_python(messages)
    dict_usage = UsageTypeAdapter.dump_python(usage)

    return {
        "agent_name": agent.name,
        "system_prompt": agent._instructions,
        "provider": agent.model.system,
        "model": agent.model.model_name,
        "tools": tools,
        "messages": dict_messages,
        "usage": dict_usage,
        "output": output,
    }


async def log_streamed_run(agent: Agent, result: StreamedRunResult) -> dict:
    """Create a log dict from a streaming run."""
    output = await result.get_output()
    usage = result.usage()
    messages = result.all_messages()
    return create_log_entry(agent=agent, messages=messages, usage=usage, output=output)


def log_run(agent: Agent, result: AgentRunResult) -> dict:
    """Create a log dict from a non-streaming run."""
    output = result.output
    usage = result.usage()
    messages = result.all_messages()
    return create_log_entry(agent=agent, messages=messages, usage=usage, output=output)


def _serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    raise TypeError(f"Type {type(obj)} not serializable")


def _find_last_timestamp(messages: list[dict]) -> datetime | None:
    # Messages come from ModelMessagesTypeAdapter.dump_python(...)
    for msg in reversed(messages):
        ts = msg.get("timestamp")
        if ts is not None:
            # ts might already be an ISO string if re-loaded from JSON
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts)
                except ValueError:
                    continue
            return ts
    return None


def save_log(entry: dict, logs_dir: str | Path | None = None) -> Path:
    """
    Save a log entry to JSON.

    - Default directory: week4/logs
      (or override with WIKIAGENT_LOGS_DIR).
    """
    base = Path(
        logs_dir
        if logs_dir is not None
        else os.environ.get("WIKIAGENT_LOGS_DIR", "week4/logs")
    )
    base.mkdir(parents=True, exist_ok=True)

    ts = _find_last_timestamp(entry["messages"]) or datetime.utcnow()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    rand_hex = secrets.token_hex(3)

    agent_name = (entry.get("agent_name") or "agent").replace(" ", "_").lower()

    filename = f"{agent_name}_{ts_str}_{rand_hex}.json"
    filepath = base / filename

    with filepath.open("w", encoding="utf-8") as f_out:
        json.dump(entry, f_out, indent=2, default=_serializer)

    return filepath
