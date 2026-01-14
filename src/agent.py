import logging
import os  # <--- NEW IMPORT
import sqlite3
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite import SqliteSaver # Memory

from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_tavily import TavilySearch
from langchain_core.messages import SystemMessage, AIMessage, trim_messages

from rag_engine import lookup_document

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vera_agent")

from budget import global_budget 

# Define State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- SYSTEM PROMPT ---
VERA_SYSTEM_PROMPT = SystemMessage(content="""
You are Vera, an AI built by tienptx.

RULES:
1. IF asked 'Who are you?', 'Who built you?', or 'Hello':
   -> ANSWER DIRECTLY. DO NOT USE TOOLS.
   
2. IF asked '2+2', 'Capital of France':
   -> ANSWER DIRECTLY. DO NOT USE TOOLS.

3. IF input is gibberish, random letters (e.g. 'asdf', 'jkl'), or unclear:
   -> STATE "I do not understand." DO NOT USE TOOLS.

4. **DOCUMENT QUERIES**:
   - IF the user asks about a "PDF", "resume", "CV", "document", or "paper":
   - -> YOU MUST USE the 'lookup_document' tool.
   - DO NOT say "I do not understand" if a file context is implied.

5. **WEB SEARCH**:
   - USE 'tavily_search_results_json' ONLY for:
     - News after 2024.
     - Specific data comparisons not found in the document.
""")

def get_vera_graph(model_name: str = "meta/llama-3.1-8b-instruct"):
    
    # --- MEMORY MANAGEMENT ---
    def trim_history(messages):
        return trim_messages(
            messages,
            max_tokens=10, 
            strategy="last",
            token_counter=len, 
            include_system=True, 
            allow_partial=False,
            start_on="human"
        )

    # --- 1. Tools ---
    # Primary Web Search Tool
    tavily_tool = TavilySearch(
        max_results=1, 
        topic="general"
    )
    
    # RAG Tool (Document Search)
    # We add lookup_document to the list so Vera can choose between Web or PDF
    tools = [tavily_tool, lookup_document]
    
    tool_node = ToolNode(tools)

    # --- 2. Model ---
    llm = ChatNVIDIA(
        model=model_name, 
        temperature=0.5
    ) 
    # Bind the FULL list of tools (Web + RAG)
    llm_with_tools = llm.bind_tools(tools)

    # --- 3. Reasoning Node ---
    def reasoning_node(state: AgentState):
        messages = state["messages"]
        
        # Guardrail: Budget Check
        if not global_budget.check_budget():
            return {
                "messages": [
                    AIMessage(content="🛑 **SYSTEM HALT**: Daily Token Budget Exceeded. Please check the dashboard.")
                ]
            }

        # Inject System Prompt
        if not isinstance(messages[0], SystemMessage):
            messages = [VERA_SYSTEM_PROMPT] + messages

        try:
            trimmed_messages = trim_history(messages)
            response = llm_with_tools.invoke(trimmed_messages)
            
            # Guardrail: Cost Update
            global_budget.update_cost(response.response_metadata)
            
            return {"messages": [response]}
            
        except Exception as e:
            logger.error(f"LLM Call Failed: {e}")
            return {
                "messages": [
                    AIMessage(content="⚠️ System Error. Please retry.")
                ]
            }

    # --- 4. Graph Construction ---
    builder = StateGraph(AgentState)
    builder.add_node("agent", reasoning_node)
    builder.add_node("tools", tool_node)
    
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    
    # --- FIX: DYNAMIC DATABASE PATH ---
    # If /app exists, we are in Docker -> Use absolute path
    # If not, we are in CI/Local -> Use relative path
    if os.path.exists("/app"):
        db_path = "/app/vera_memory.sqlite"
    else:
        db_path = "vera_memory.sqlite"

    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)

    return builder.compile(checkpointer=memory)