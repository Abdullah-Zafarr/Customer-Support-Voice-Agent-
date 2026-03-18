import json
from groq import AsyncGroq
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi.concurrency import run_in_threadpool

from ..core.config import settings
from ..core.logger import logger
from ..db.database import SessionLocal, SupportTicket # We'll reuse SupportTicket table for Inquiry logging to avoid model migration overhead right now
from .rag import query_knowledge
from .settings_manager import load_settings

# Initialize AsyncGroq client
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile"

def manage_inquiry_db(name: str, inquiry_type: str, notes: str, ticket_id: Optional[int] = None) -> dict:
    """Create or update a patient inquiry/booking in the database."""
    if not notes or not notes.strip():
        return {
            "status": "rejected",
            "message": "Cannot create an inquiry without notes. Please ask the patient what they need."
        }
    
    db = SessionLocal()
    try:
        # Re-using the SupportTicket table rows for inquiries
        if ticket_id:
            ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
            if ticket:
                ticket.customer_name = name
                ticket.issue_description = f"[{inquiry_type}] {notes}"
                db.commit()
                db.refresh(ticket)
                return {
                    "status": "success",
                    "action": "updated",
                    "ticket_id": ticket.id,
                    "message": f"Inquiry #{ticket.id} updated."
                }
                
        new_ticket = SupportTicket(
            customer_name=name,
            issue_description=f"[{inquiry_type}] {notes}",
            urgency="medium",
            created_at=datetime.now()
        )
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        
        return {
            "status": "success",
            "action": "created",
            "ticket_id": new_ticket.id,
            "created_at": new_ticket.created_at.isoformat(),
            "message": f"Inquiry logged for {name}."
        }
    except Exception as e:
        logger.error(f"Failed to manage inquiry: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

# Define the tools (function calling)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "log_inquiry",
            "description": "Log a patient inquiry, booking request, or callback request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The full name of the patient."
                    },
                    "inquiry_type": {
                        "type": "string",
                        "enum": ["booking", "general_question", "referral_query", "callback"],
                        "description": "The category of the inquiry."
                    },
                    "notes": {
                        "type": "string",
                        "description": "A descriptive note of what the patient needs or scheduled."
                    },
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of an existing inquiry to update if you've already created one."
                    }
                },
                "required": ["name", "inquiry_type", "notes"]
            }
        }
    }
]

async def process_llm_turn(messages: List[Dict[str, Any]]) -> dict:
    """Process a turn with the LLM and handle function calling if needed."""
    
    # Build system prompt with optional RAG context
    system_prompt = SYSTEM_PROMPT
    
    # Find the latest user message for RAG retrieval
    latest_user_msg = None
    for m in reversed(messages):
        if m.get("role") == "user":
            latest_user_msg = m.get("content", "")
            break
    
async def process_llm_turn(messages: List[Dict[str, Any]]) -> dict:
    """Process a turn with the LLM and handle function calling if needed."""
    
    current_settings = load_settings()
    system_prompt = current_settings.get("system_prompt")
    temperature = current_settings.get("temperature", 0.7)
    
    # Find the latest user message for RAG retrieval
    latest_user_msg = None
    for m in reversed(messages):
        if m.get("role") == "user":
            latest_user_msg = m.get("content", "")
            break
    
    if latest_user_msg:
        try:
            chunks = await run_in_threadpool(query_knowledge, latest_user_msg)
            if chunks:
                context_text = "\n\n".join(
                    f"[Source: {c['source']}]\n{c['text']}" for c in chunks
                )
                system_prompt += f"\n\nKNOWLEDGE CONTEXT:\n{context_text}\n"
                logger.info(f"RAG: Injected {len(chunks)} chunks into prompt.")
        except Exception as e:
            logger.warning(f"RAG retrieval failed (non-fatal): {e}")
    
    # Ensure system prompt is present (or update it)
    sys_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system"), None)
    if sys_idx is not None:
        messages[sys_idx]["content"] = system_prompt
    else:
        messages.insert(0, {"role": "system", "content": system_prompt})
        
    try:
        response = await groq_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=temperature,
            max_tokens=200,
        )
        
        response_message = response.choices[0].message
        
        # Check if LLM wants to call a function
        tool_calls = response_message.tool_calls
        if tool_calls:
            messages.append(response_message)
            tool_calls_info = []
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                
                if function_name == "log_inquiry":
                    function_args = json.loads(tool_call.function.arguments)
                    logger.info(f"LLM called tool {function_name} with args: {function_args}")
                    
                    function_response = manage_inquiry_db(
                        name=function_args.get("name"),
                        inquiry_type=function_args.get("inquiry_type", "general_question"),
                        notes=function_args.get("notes"),
                        ticket_id=function_args.get("ticket_id")
                    )
                    
                    tool_calls_info.append({
                        "name": function_name,
                        "result": {
                            "name": function_args.get("name"),
                            "inquiry_type": function_args.get("inquiry_type"),
                            "notes": function_args.get("notes"),
                            "id": function_response.get("ticket_id")
                        }
                    })
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(function_response)
                    })
                    
            # Call LLM again to generate reply based on tool response
            second_response = await groq_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=200
            )
            return {
                "response": second_response.choices[0].message.content,
                "tool_calls": tool_calls_info
            }
        
        return {
            "response": response_message.content,
            "tool_calls": []
        }

    except Exception as e:
        logger.error(f"Error calling Groq LLM: {e}")
        return {
            "response": "I'm sorry, I'm having trouble processing that right now.",
            "tool_calls": []
        }
