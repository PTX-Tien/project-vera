import os
import json
import uuid
import shutil
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

# Import Graph Logic
from agent import get_vera_graph
from rag_engine import process_document

# --- FIX: Use In-Memory Checkpointer (Stable) ---
from langgraph.checkpoint.memory import MemorySaver

# --- GLOBAL VARIABLES ---
graph = None  # Will be initialized on startup

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    print("✅ Initializing In-Memory Persistence...")
    
    # Use MemorySaver instead of SQLite to avoid the 'is_alive' bug
    memory = MemorySaver()
    
    # Build Graph with this memory
    graph = get_vera_graph(memory=memory)
    print("✅ Graph initialized successfully.")
    
    yield  # Application runs here
    
    print("🛑 Shutting down...")

# --- APP SETUP ---
app = FastAPI(title="Project Vera API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define Input Structure
class ChatRequest(BaseModel):
    message: str
    thread_id: str = None

# --- ENDPOINTS ---

@app.get("/health")
def health_check():
    return {"status": "active", "model": "Llama 3 8B", "mode": "Memory"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_location = f"/tmp/{file.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        
        process_document(file_location)
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Use await because the graph is async
        response = await graph.ainvoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config
        )
        ai_message = response["messages"][-1].content
        return {"response": ai_message, "thread_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        thread_id = request.thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        # Stream events
        async for event in graph.astream_events(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
            version="v1"
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield f"data: {json.dumps({'token': content})}\n\n"
                    
    return StreamingResponse(event_generator(), media_type="text/event-stream")