from fastapi import FastAPI, Query, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging
import os
from dotenv import load_dotenv

from function_chatbot import handle_fixed_questions, handle_file_upload
from database import db_manager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Nidhaan Healthcare API",
    description="API for handling user queries and file uploads",
    version="2.0.0"
)

origins = [
    "http://localhost:8080",
    "http://localhost:8000",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://localhost:63342"
]

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint to check API status"""
    return {
        "message": "Nidhaan Healthcare API is running",
        "version": app.version,
        "status": "active"
    }

@app.get("/query/")
async def handle_user_query(user_input: str = Query(..., description="The user's query")):
    """Handle text-only user queries"""
    if not user_input or not user_input.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        user_input = user_input.strip()
        logger.info(f"Processing text query: {user_input[:50]}...")
        
        previous_chats = db_manager.get_last_two_chats()
        response = handle_fixed_questions(user_input, previous_chats)

        response_text = response.get("answer", "No response generated")
        db_manager.insert_chat(user_input, response_text)
        
        return {"response": response}
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while processing query")

@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    user_query: Optional[str] = Query(None, description="Optional user query with file")
):
    """Handle file uploads with optional text query"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        contents = await file.read()

        # Enforce 10MB size limit
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB")

        await file.seek(0)  # Reset file pointer
        query_text = user_query.strip() if user_query else ""

        logger.info(f"Processing file upload: {file.filename}, Query: {'Yes' if query_text else 'No'}")

        previous_chats = db_manager.get_last_two_chats()
        response = handle_file_upload(contents, file.filename, query_text, previous_chats)

        # Store in database
        user_input = f"[FILE: {file.filename}]" + (f" {query_text}" if query_text else "")
        response_text = response.get("answer", "No response generated")
        db_manager.insert_chat(user_input, response_text)

        return {"response": response}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file upload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while processing file")

@app.get("/clear-history/")
async def clear_chat_history():
    """Clear all chat history (called when frontend closes or refreshes)"""
    try:
        db_manager.clear_chat_history()
        return {"message": "Chat history cleared successfully", "status": "success"}
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(status_code=500, detail="Error clearing chat history")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running normally"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
