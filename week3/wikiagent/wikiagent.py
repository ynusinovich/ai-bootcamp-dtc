import os
from pydantic import BaseModel, Field
from typing import List
from pydantic_ai import Agent, AgentRunResult, UsageLimits

from .tools import search_wikipedia, get_page_raw


class WikiAnswer(BaseModel):
    """Final answer schema from the agent."""
    answer: str = Field(..., description="Concise, factual answer in 1–3 paragraphs.")
    references: List[str] = Field(default_factory=list, description="List of Wikipedia URLs used.")

INSTRUCTIONS = """
You are a careful research agent that MUST:
1) Call the `search_wikipedia` tool FIRST with the user question to discover candidate pages.
2) From the search results, pick 2–5 promising page titles and call `get_page_raw` on each BEFORE composing a final answer.
3) Base your answer ONLY on what you read in those pages. If unclear, say so.
4) Return 2–5 'references' as canonical Wikipedia URLs you actually fetched.
5) Be concise and neutral. Avoid speculation.
"""

agent: Agent[None, WikiAnswer] = Agent(
    'openai:gpt-4o-mini',
    instructions=INSTRUCTIONS,
    output_type=WikiAnswer,
    tools=[search_wikipedia, get_page_raw],  # plain functions are allowed
)

REQ_LIMIT = int(os.getenv("WIKIAGENT_REQUEST_LIMIT", "12"))
TOOL_LIMIT = int(os.getenv("WIKIAGENT_TOOL_CALLS_LIMIT", "12"))


def run_sync(question: str) -> AgentRunResult[WikiAnswer]:
    """Run the agent once, with sane usage caps."""
    return agent.run_sync(
        question,
        usage_limits=UsageLimits(request_limit=REQ_LIMIT, tool_calls_limit=TOOL_LIMIT)
    )
