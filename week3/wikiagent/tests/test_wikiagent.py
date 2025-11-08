import re
from pydantic_ai import AgentRunResult
from wikiagent import run_sync
from typing import List, Dict


def _tool_calls(result: AgentRunResult):
    calls = []
    for m in result.new_messages():
        for p in m.parts:
            if getattr(p, "part_kind", "") == "tool-call":
                calls.append({"name": p.tool_name, "args": p.args})
    return calls


def test_invokes_search_and_multiple_get_page():
    result = run_sync("where do capybaras live?")

    calls = _tool_calls(result)
    names = [c["name"] for c in calls]

    # at least one search
    assert any(n == "search_wikipedia" for n in names), "search_wikipedia was not called"

    # get_page_raw multiple times
    get_calls = sum(n == "get_page_raw" for n in names)
    assert get_calls >= 2, f"expected >=2 get_page_raw calls, got {get_calls}"


def test_references_present_and_look_like_wiki_urls():
    result = run_sync("where do capybaras live?")
    refs: List[str] = result.output.references

    assert len(refs) >= 1, "Expected at least one reference"
    for url in refs:
        assert "wikipedia.org/wiki/" in url, f"Unexpected reference format: {url}"


def test_answer_not_empty():
    result = run_sync("where do capybaras live?")
    assert result.output.answer.strip(), "Empty answer"


def _judge_sequence_and_refs(result: AgentRunResult) -> Dict[str, bool]:
    calls = _tool_calls(result)
    names = [c["name"] for c in calls]
    out = result.output

    search_first = len(names) > 0 and names[0] == "search_wikipedia"
    get_count = sum(n == "get_page_raw" for n in names)
    get_range_ok = 2 <= get_count <= 5

    refs_ok = isinstance(out.references, list) and len(out.references) >= 1
    refs_fmt_ok = all("wikipedia.org/wiki/" in r for r in out.references)

    return {
        "search_first": search_first,
        "get_range_ok": get_range_ok,
        "refs_ok": refs_ok and refs_fmt_ok,
    }


def test_judge_search_first_and_get_page_range_and_references():
    # Use a stable, well-linked topic so 2–5 pages is realistic
    result = run_sync("where do capybaras live?")

    verdict = _judge_sequence_and_refs(result)
    assert verdict["search_first"], "Expected search_wikipedia to be the first tool call"
    assert verdict["get_range_ok"], "Expected 2–5 get_page_raw calls before answering"
    assert verdict["refs_ok"], "Expected at least one Wikipedia reference URL"