import json
from groq import AsyncGroq
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi.concurrency import run_in_threadpool

from ..core.config import settings
from ..core.logger import logger
from ..db.database import SessionLocal, SupportTicket
from .rag import query_knowledge

# Initialize AsyncGroq client
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a professional AI Customer Support Agent.
Your job is to greet the caller, understand their issue, and log/update a support ticket.
Be warm, conversational, and efficient — you're speaking over the phone.
Ask ONE question at a time. Keep responses under 2 sentences.

IMPORTANT RULES:
- Do NOT create a ticket until you have BOTH the customer's name AND a description of their issue.
- If you only have the name, ask for the issue first. Never create a ticket with an empty issue.
- If KNOWLEDGE CONTEXT is provided below, use it to answer the user's questions accurately. Base your answers on the provided context. If the context doesn't cover the question, say you don't have that information right now.

Flow:
1. Greet the caller and ask for their name.
2. Ask them to describe their issue briefly.
3. ONLY after you have both name AND issue, use the `manage_ticket` tool to log the ticket.
4. If they give more information later, use the `manage_ticket` tool AGAIN with the same `ticket_id` to update the existing ticket. Do NOT create a new ticket.
5. Confirm the ticket was created/updated and ask if there's anything else.

Never give long explanations. Be concise and helpful.
"""

def manage_ticket_db(name: str, issue: str, urgency: str, ticket_id: Optional[int] = None) -> dict:
    """Create or update a support ticket in the database."""
    # Guard: reject tickets with no issue description
    if not issue or not issue.strip():
        return {
            "status": "rejected",
            "message": "Cannot create a ticket without an issue description. Please ask the customer for their issue first."
        }
    
    db = SessionLocal()
    try:
        if ticket_id:
            ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
            if ticket:
                ticket.customer_name = name
                ticket.issue_description = issue
                ticket.urgency = urgency
                db.commit()
                db.refresh(ticket)
                return {
                    "status": "success",
                    "action": "updated",
                    "ticket_id": ticket.id,
                    "message": f"Support ticket #{ticket.id} updated."
                }
                
        new_ticket = SupportTicket(
            customer_name=name,
            issue_description=issue,
            urgency=urgency,
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
            "message": f"Support ticket #{new_ticket.id} created for {name}."
        }
    except Exception as e:
        logger.error(f"Failed to manage ticket: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

# Define the tools (function calling)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_ticket",
            "description": "Create or update a customer support ticket to log the caller's issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The full name of the customer."
                    },
                    "issue": {
                        "type": "string",
                        "description": "A comprehensive description of the customer's issue. Include accumulated details."
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "emergency"],
                        "description": "The estimated urgency level of the issue."
                    },
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of an existing ticket to update (if you have already created one in this conversation)."
                    }
                },
                "required": ["name", "issue", "urgency"]
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
            temperature=0.7,
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
                
                if function_name == "manage_ticket":
                    function_args = json.loads(tool_call.function.arguments)
                    logger.info(f"LLM called tool {function_name} with args: {function_args}")
                    
                    function_response = manage_ticket_db(
                        name=function_args.get("name"),
                        issue=function_args.get("issue"),
                        urgency=function_args.get("urgency", "medium"),
                        ticket_id=function_args.get("ticket_id")
                    )
                    
                    tool_calls_info.append({
                        "name": function_name,
                        "result": {
                            "name": function_args.get("name"),
                            "issue": function_args.get("issue"),
                            "urgency": function_args.get("urgency", "medium"),
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
                temperature=0.7,
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
