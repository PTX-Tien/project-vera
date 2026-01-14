import shutil # Add this import at the top
from rag_engine import process_document # Add this import

import streamlit as st
import os
from dotenv import load_dotenv

# Import the graph and the budget manager
from agent import get_vera_graph
from budget import global_budget # <--- Correct Import

# Load environment variables from .env file
load_dotenv()

st.set_page_config(page_title="Project Vera", layout="wide")

# --- SIDEBAR (BUDGET CONTROL) ---
with st.sidebar:
    st.title("⚙️ Control Panel")
    
    # --- NEW: FILE UPLOADER ---
    st.subheader("📁 Knowledge Base")
    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
    
    if uploaded_file is not None:
        # Save file locally so PyPDFLoader can read it
        save_path = f"/tmp/{uploaded_file.name}"
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Process the file (only do it once per file to save time)
        if "last_uploaded" not in st.session_state or st.session_state.last_uploaded != uploaded_file.name:
            with st.spinner("Processing document..."):
                process_document(save_path)
                st.session_state.last_uploaded = uploaded_file.name
                st.success("Document Index Ready! 🧠")

    st.divider()
    st.subheader("💳 Token Budget")
    
    # Calculate usage percentage
    # Avoid division by zero if limit is 0
    limit = global_budget.limit if global_budget.limit > 0 else 1
    usage_percent = min(global_budget.used / limit, 1.0)
    
    # Color logic
    if usage_percent < 0.5:
        bar_color = "green"
    elif usage_percent < 0.8:
        bar_color = "orange"
    else:
        bar_color = "red"
        
    st.progress(usage_percent)
    st.caption(f"Status: {global_budget.get_status()}")
    
    if st.button("Reset Budget 🔄"):
        global_budget.used = 0
        st.rerun()

# --- MAIN APP ---
st.title("Project Vera 🧬")
st.caption("Automated Reasoning & Research Synthesis Engine")

# Initialize Graph (Cached)
@st.cache_resource
def load_graph():
    return get_vera_graph()

graph = load_graph()

# Session State for History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat History
for msg in st.session_state.messages:
    if msg["role"] != "tool":
        st.chat_message(msg["role"]).write(msg["content"])

# User Input
if prompt := st.chat_input("Enter research topic..."):
    # 1. Update UI immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # 2. Prepare Inputs
    # We send ONLY the user input. Agent.py handles the System Prompt.
    inputs = {"messages": [("user", prompt)]}

    # --- MEMORY CONFIGURATION (Path B) ---
    # "thread_id" tells the database which conversation history to load.
    # Using a static ID like "admin_user_1" means Vera will remember YOU forever,
    # even if you restart the Docker container.
    config = {
        "configurable": {"thread_id": "admin_user_1"},
        "recursion_limit": 15
    }

    # 3. Stream Response
    with st.chat_message("assistant"):
        with st.status("🧠 Vera is thinking...", expanded=True) as status:
            
            response_container = st.empty()
            full_response = ""
            
            # Stream events using the config with thread_id
            for event in graph.stream(inputs, config=config):
                for node, values in event.items():
                    
                    if node == "agent":
                        last_msg = values["messages"][-1]
                        
                        if last_msg.tool_calls:
                            tool_name = last_msg.tool_calls[0]['name']
                            query = last_msg.tool_calls[0]['args'].get('query', 'data')
                            status.write(f"🔍 Decided to search {tool_name} for: *'{query}'*")
                            status.update(label="🌍 Vera is exploring the web...", state="running")
                        else:
                            status.write("💡 Research complete. Synthesizing answer...")
                            status.update(label="✅ Research Finished", state="complete", expanded=False)
                            
                            full_response = last_msg.content
                            response_container.markdown(full_response)
                            
                            # Optional: Force rerun to update budget bar
                            # st.rerun() 
                    
                    elif node == "tools":
                        status.write("📄 Reading search results...")

            if not full_response: 
                # Catch empty responses or errors
                pass
    
    # 4. Save Response
    st.session_state.messages.append({"role": "assistant", "content": full_response})