# Langchain imports
from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

# Helper imports
from dotenv import load_dotenv

# Tavily imports
from tavily import TavilyClient

from typing import Dict, Any

# ----------- Loading Env Variables -----------
load_dotenv()

# ----------- Configuring the agent -----------

# System prompt
SYS_PROMPT = """
You are a personal chef assistant.
You use the web_search tool to search the web for recipes
that match the ingredients someone asks you about.
"""


# Tools
@tool
def web_search(query: str) -> Dict[str, Any]:
    """Search the web for recipes"""

    web_client = TavilyClient()

    return web_client.search(query)


# Memory
checkpointer = InMemorySaver()

# Defining the agent
agent = create_agent(
    model='claude-sonnet-5',
    system_prompt=SYS_PROMPT,
    checkpointer=checkpointer,
    tools=[web_search]
)
