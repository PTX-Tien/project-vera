import logging
import uuid
import re  # <--- NEW IMPORT
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_tavily import TavilySearch
from langchain_core.messages import SystemMessage, AIMessage, trim_messages

from rag_engine import lookup_document, is_document_uploaded 
from budget import global_budget 

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vera_agent")

# Define State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- SYSTEM PROMPTS ---
PROMPT_WITH_DOC = SystemMessage(content="""
You are Vera, an AI Research Agent.
A PDF document is currently uploaded.
RULES:
1. If the user asks about the document/candidate -> USE 'lookup_document'.
2. If the user shares personal info ("My name is...") -> Just remember it. DO NOT search.
""")

PROMPT_NO_DOC = SystemMessage(content="""
You are Vera, an AI Research Agent.
NO document is currently uploaded.
RULES:
1. Answer general questions directly.
2. If the user shares personal info ("My name is...") -> Just remember it. DO NOT search.
3. If the user asks to "summarize" or "search the file", politely reply: "Please upload a document first."
""")

def get_vera_graph(model_name: str = "meta/llama-3.1-8b-instruct", memory=None):
    
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
    tavily_tool = TavilySearch(max_results=1, topic="general")
    tools_all = [tavily_tool, lookup_document] 
    tools_web_only = [tavily_tool]             
    tool_node = ToolNode(tools_all)

    # --- 2. Model ---
    llm = ChatNVIDIA(model=model_name, temperature=0.5) 

    # --- 3. Reasoning Node (The Brain) ---
    def reasoning_node(state: AgentState):
        messages = state["messages"]
        
        # Guardrail: Budget Check
        if not global_budget.check_budget():
            return {"messages": [AIMessage(content="🛑 **SYSTEM HALT**: Daily Token Budget Exceeded.")]}

        # --- DYNAMIC LOGIC START ---
        has_doc = is_document_uploaded()
        
        # 1. Select Prompt
        current_prompt = PROMPT_WITH_DOC if has_doc else PROMPT_NO_DOC
        if isinstance(messages[0], SystemMessage):
            messages[0] = current_prompt 
        else:
            messages = [current_prompt] + messages 

        # 2. INTELLIGENT FILTERS
        last_msg_text = messages[-1].content.lower().strip()
        
        # Filter A: Chitchat (Greetings)
        chitchat_triggers = ["hello", "hi", "hey", "hola", "greetings", "good morning", "who are you"]
        is_chitchat = any(last_msg_text.startswith(t) for t in chitchat_triggers) and len(last_msg_text) < 20

        # Filter B: Personal Info (My name is...) - NEW!
        # If user says "My name is X", we disable tools so it DOES NOT search.
        personal_patterns = [
            r"my name is",
            r"i am",
            r"call me",
            r"i'm",
            r"my email is"
        ]
        is_personal = any(re.search(p, last_msg_text) for p in personal_patterns)

        # 3. Bind Tools Accordingly
        if is_chitchat or is_personal:
            # FORCE: Pure LLM response (No Search)
            llm_active = llm
        elif has_doc:
            # PDF Mode: RAG + Web
            llm_active = llm.bind_tools(tools_all)
        else:
            # Web Mode: Web only
            llm_active = llm.bind_tools(tools_web_only)
        # ----------------------------

        try:
            trimmed_messages = trim_history(messages)
            response = llm_active.invoke(trimmed_messages)
            global_budget.update_cost(response.response_metadata)
            return {"messages": [response]}
            
        except Exception as e:
            logger.error(f"LLM Call Failed: {e}")
            return {"messages": [AIMessage(content=f"⚠️ System Error: {str(e)}")]}

    # --- 4. Fast Path Optimization ---
    def route_start(state: AgentState):
        last_msg = state["messages"][-1].content.lower()
        fast_keywords = ["pdf", "resume", "cv", "document", "file", "candidate", "skills"]
        
        if is_document_uploaded() and any(k in last_msg for k in fast_keywords):
            return "fast_doc_trigger"
        
        return "agent"

    def fast_doc_trigger(state: AgentState):
        last_user_msg = state["messages"][-1].content
        tool_call_id = str(uuid.uuid4())
        fast_tool_msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "lookup_document",
                "args": {"query": last_user_msg},
                "id": tool_call_id
            }]
        )
        return {"messages": [fast_tool_msg]}

    # --- 5. Graph Construction ---
    builder = StateGraph(AgentState)
    builder.add_node("agent", reasoning_node)
    builder.add_node("tools", tool_node)
    builder.add_node("fast_doc_trigger", fast_doc_trigger)
    
    builder.add_conditional_edges(START, route_start, {"fast_doc_trigger": "fast_doc_trigger", "agent": "agent"})
    builder.add_edge("fast_doc_trigger", "tools")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    
    return builder.compile(checkpointer=memory)