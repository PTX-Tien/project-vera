import logging
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_tavily import TavilySearch
from langchain_core.messages import SystemMessage, AIMessage, trim_messages
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver # <--- NEW IMPORT

from budget import global_budget
# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vera_agent")

# Define State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- OPTIMIZED SYSTEM PROMPT (Short & Strict for 8B Model) ---
VERA_SYSTEM_PROMPT = SystemMessage(content="""
You are Vera, an AI built by tienptx.

RULES:
1. IF asked 'Who are you?', 'Who built you?', or 'Hello':
   -> ANSWER DIRECTLY. DO NOT USE TOOLS.
   
2. IF asked '2+2', 'Capital of France':
   -> ANSWER DIRECTLY. DO NOT USE TOOLS.

3. IF input is gibberish, random letters (e.g. 'asdf', 'jkl'), or unclear:
   -> STATE "I do not understand." DO NOT USE TOOLS.

4. ONLY use search for:
   - News after 2024.
   - Specific data comparisons.
""")

def get_vera_graph(model_name: str = "meta/llama-3.3-70b-instruct"):
    
    # --- SURVIVAL MECHANISM 1: MEMORY MANAGEMENT ---
    def trim_history(messages):
        return trim_messages(
            messages,
            # Keep last 10 messages (safe limit)
            max_tokens=10, 
            strategy="last",
            token_counter=len, 
            include_system=True, 
            allow_partial=False,
            start_on="human"
        )

    # --- 1. Tools ---
    # FIX: Reduce results to 1 to prevent timeout crashes
    tool = TavilySearch(
        max_results=1, 
        topic="general"
    )
    tools = [tool]
    tool_node = ToolNode(tools)

    # --- 2. Model ---
    # FIX: Add timeout=60 to prevent connection drops on slow networks
    llm = ChatNVIDIA(
        model=model_name, 
        temperature=0.5,
    ) 
    llm_with_tools = llm.bind_tools(tools)

    # --- 3. Reasoning Node ---
    def reasoning_node(state: AgentState):
        messages = state["messages"]
        
        # --- GUARDRAIL 1: DENIAL OF WALLET CHECK ---
        if not global_budget.check_budget():
            return {
                "messages": [
                    AIMessage(content="🛑 **SYSTEM HALT**: Daily Token Budget Exceeded. Please check the dashboard.")
                ]
            }

        # Inject System Prompt logic (keep your existing code here)
        if not isinstance(messages[0], SystemMessage):
            messages = [VERA_SYSTEM_PROMPT] + messages

        try:
            trimmed_messages = trim_history(messages)
            
            # Invoke Model
            response = llm_with_tools.invoke(trimmed_messages)
            
            # --- GUARDRAIL 2: UPDATE THE BILL ---
            # We grab the metadata from the raw response to count costs
            global_budget.update_cost(response.response_metadata)
            
            return {"messages": [response]}
            
        except Exception as e:
            logger.error(f"LLM Call Failed: {e}")
            return {
                "messages": [
                    AIMessage(content="⚠️ System Error. Please retry.")
                ]
            }

    # --- 4. Graph Construction with MEMORY ---
    builder = StateGraph(AgentState)
    builder.add_node("agent", reasoning_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    
    # --- NEW: SETUP DATABASE CONNECTION ---
    # We verify if the DB file exists, if not it creates it.
    
    # check_same_thread=False is needed for Streamlit's multi-threading
    #conn = sqlite3.connect("vera_memory.sqlite", check_same_thread=False)
    
    # Use absolute path inside the container
    conn = sqlite3.connect("/app/vera_memory.sqlite", check_same_thread=False)
    memory = SqliteSaver(conn)

    # Compile the graph WITH the memory checkpointer
    return builder.compile(checkpointer=memory)