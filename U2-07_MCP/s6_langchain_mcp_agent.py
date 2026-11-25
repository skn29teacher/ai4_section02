import asyncio
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage,SystemMessage,ToolMessage
from langchain_mcp_adapters.tools import load_mcp_tools