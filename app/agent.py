import json
from groq import AsyncGroq
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .config import settings
from .logger import logger
from .database import SessionLocal, Appointment

# Initialize AsyncGroq client
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile" # Lighting fast Groq model

SYSTEM_PROMPT = """You are an AI Voice Agent for a home services company (HVAC and Plumbing).
Your goal is to briefly chat with the customer, understand their issue, and book an appointment for them.
Be highly conversational, brief, and concise as you are speaking over the phone.
Ask ONE question at a time.
First, ask for their name.
Then, ask for a brief description of their issue.
Once you have the name and issue, use the `book_appointment` tool to schedule an appointment.

Do NOT provide long explanations. Keep responses under 2-3 sentences max.
"""

def book_appointment_db(name: str, issue: str, urgency: str) -> dict:
    """Mock database operation to book an appointment."""
    db = SessionLocal()
    try:
        # Simple scheduling logic: book for tomorrow
        scheduled_time = datetime.now() + timedelta(days=1)
        
        new_app = Appointment(
            customer_name=name,
            issue_description=issue,
            urgency=urgency,
            scheduled_time=scheduled_time
        )
        db.add(new_app)
        db.commit()
        db.refresh(new_app)
        
        return {
            "status": "success",
            "appointment_id": new_app.id,
            "scheduled_time": scheduled_time.isoformat(),
            "message": f"Appointment booked for {name} regarding {issue}."
        }
    except Exception as e:
        logger.error(f"Failed to book appointment: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

# Define the tools (function calling)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a service appointment for a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The full name of the customer."
                    },
                    "issue": {
                        "type": "string",
                        "description": "A brief description of the plumbing or HVAC issue."
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "emergency"],
                        "description": "The estimated urgency of the issue."
                    }
                },
                "required": ["name", "issue", "urgency"]
            }
        }
    }
]

async def process_llm_turn(messages: List[Dict[str, Any]]) -> dict:
    """Process a turn with the LLM and handle function calling if needed."""
    
    # Ensure system prompt is present
    if not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        
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
            messages.append(response_message) # Add assistant's tool call request
            tool_calls_info = []
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                
                if function_name == "book_appointment":
                    function_args = json.loads(tool_call.function.arguments)
                    logger.info(f"LLM called tool {function_name} with args: {function_args}")
                    
                    # Execute the function
                    function_response = book_appointment_db(
                        name=function_args.get("name"),
                        issue=function_args.get("issue"),
                        urgency=function_args.get("urgency", "medium")
                    )
                    
                    # Store info for frontend
                    tool_calls_info.append({
                        "name": function_name,
                        "result": {
                            "name": function_args.get("name"),
                            "issue": function_args.get("issue"),
                            "urgency": function_args.get("urgency", "medium"),
                            "id": function_response.get("appointment_id")
                        }
                    })
                    
                    # Push the result back to messages
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
