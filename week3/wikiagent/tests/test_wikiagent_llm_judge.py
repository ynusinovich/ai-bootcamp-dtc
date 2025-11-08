import os
import pytest
from pydantic import BaseModel
from pydantic_ai import Agent, AgentRunResult, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel  # or use model string
from wikiagent import run_sync


class Verdict(BaseModel):
    search_first: bool
    got_2_to_5_pages: bool
    references_present: bool


def _log_text(result: AgentRunResult) -> str:
    lines = []
    for m in result.new_messages():
        for p in getattr(m, "parts", []):
            if getattr(p, "part_kind", "") == "tool-call":
                lines.append(f"CALL {p.tool_name}({p.args})")
            elif getattr(p, "part_kind", "") == "assistant-tool-result":
                lines.append(f"RESULT {getattr(p, 'tool_name', '')}")
    return "\n".join(lines)


@pytest.mark.skipif(not os.getenv("JUDGE_WITH_LLM"), reason="Set JUDGE_WITH_LLM=1 to run LLM judge")
def test_llm_judge_sequence_and_refs():
    run = run_sync("where do capybaras live?")
    log_text = _log_text(run)  # type: ignore
    refs_text = "\n".join(run.output.references)

    judge = Agent(
        model=OpenAIChatModel("gpt-4o-mini"),  # or: Agent('openai:gpt-4o-mini', ...)
        instructions=(
            "You will receive:\n"
            "1) A list of TOOL CALLS (chronological)\n"
            "2) The final output REFERENCES (URLs)\n\n"
            "Answer strictly with JSON (search_first, got_2_to_5_pages, references_present) "
            "according to these rules:\n"
            "- search_first: TRUE iff the first tool call is `search_wikipedia`.\n"
            "- got_2_to_5_pages: TRUE iff there are between 2 and 5 calls to `get_page_raw`.\n"
            "- references_present: TRUE iff there is at least 1 reference URL containing 'wikipedia.org/wiki/'."
        ),
        output_type=Verdict,
    )

    # Pass everything as the user prompt (no `input=` kw)
    prompt = (
        "Judge the run.\n\n"
        "TOOL CALLS:\n" + log_text + "\n\n"
        "REFERENCES:\n" + refs_text + "\n"
    )

    verdict = judge.run_sync(
        prompt,
        usage_limits=UsageLimits(request_limit=2),
    ).output

    assert verdict.search_first, "LLM judge: expected search first"
    assert verdict.got_2_to_5_pages, "LLM judge: expected 2–5 page fetches"
    assert verdict.references_present, "LLM judge: expected at least one reference URL"
