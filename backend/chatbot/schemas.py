from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Literal, Optional, Union
from datetime import datetime


class ChatRequest(BaseModel):
    
    query: str = Field(..., description="The text query from the user")
    thread_id: Optional[str] = Field(None, 
    description="Unique chat thread identifier. If omitted, a new chat thread will be created")

class StreamTokenData(BaseModel):
    token: str = Field(..., description="A single text chunk from the model")

class StreamMetadata(BaseModel):
    """Data payload sent once at the end of a stream with execution metadata"""
    thread_id: str = Field(..., description="Thread identifier for this chat")
    total_tokens: int = Field(..., description="Total number of tokens processed")
    execution_time_ms: int = Field(..., description="Time in milliseconds for response generation")
    intent: Literal["Conversational","Coding"] = Field(..., description="The classified intent for the query")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Assistant's final response in markdown")
    intent: str = Field(..., description="The classified intent for the query (Conversational / Coding)")
    thread_id: str = Field(..., description="The session/thread ID for this chat")
    metadata: Optional[StreamMetadata] = Field(None, description="Execution and token usage metadata")

class StreamErrorData(BaseModel):
    message: str = Field(..., description="A user friendly error message")

class StreamEvent(BaseModel):
    """A single Server-Sent Event emitted during chat_stream.

    The ``event`` field determines the shape of ``data``:
      - ``token``     -> ``StreamTokenData``
      - ``metadata``  -> ``StreamMetadata``
      - ``interrupt`` -> ``StreamInterruptData``
      - ``error``     -> ``StreamErrorData``
    """
    event: Literal["token", "metadata", "interrupt", "error"] = Field(..., description="The type of event")
    data: Dict[str, Any] = Field(..., description="The event payload (shape depends on event type)")


class StreamInterruptData(BaseModel):
    """Payload emitted when the graph pauses at human_review_node."""
    thread_id: str = Field(..., description="Session thread ID needed to resume")
    generated_code: str = Field(..., description="The code produced so far")
    test_results: str = Field(..., description="Pytest output from the sandbox run")
    tests_passed: bool = Field(..., description="Whether all tests passed")
    message: str = Field(default="Please review the generated code and provide feedback.")


class ReviewRequest(BaseModel):
    """Body for POST /chatbot/review/{thread_id}"""
    approved: bool = Field(..., description="True = accept code and finalize, False = regenerate")
    feedback: str = Field(default="", description="Optional feedback for the regeneration step")

class MessageSchema(BaseModel):
    """A single message inside a conversational thread """
    role: str = Field(..., description = "Role of the sender (user, assistant, system)")
    content: str = Field(..., description="Text content of the message")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of the message creation")

class HistoryResponse(BaseModel):
    """ A full conversational history for a given thread"""
    thread_id: str = Field(..., description = "The session/thread identifier")
    messages: List[MessageSchema] = Field(
        ..., description="Chronological log of chat history"
    )

class ThreadSchema(BaseModel):
    """Summary view of a single conversation thread"""
    thread_id: str = Field(..., description="Unique chat identifier")
    preview: str = Field(..., description="A short preview of the text")
    intent: str = Field(..., description="The last classified intent (Conversational, Coding)")
    updated_at : datetime = Field(..., description="ISO timestamp of the last message update")

class ThreadResponse(BaseModel):
    """Collection of all the threads belonging to the authenticated user"""
    threads: List[ThreadSchema] = Field(..., description="List of all available threads for the user")

class TestResult(BaseModel):
    test_result: str = Field(..., description="The test summary of the generated code")
    tests_passed: bool = Field(..., description="Test cases passed or failed")
    retry_count: int = Field(0, description="Retry count for the code execution")


class ReflectionResult(BaseModel):
    """Structured output from the reflection/debugging node."""
    summary_of_failures: str = Field(
        ..., description="Brief bullet-point summary of what failed"
    )
    root_cause_analysis: str = Field(
        ..., description="Why each failure occurred in the code"
    )
    remediation_plan: str = Field(
        ..., description="Clear, actionable steps to fix all identified defects"
    )

    @field_validator("summary_of_failures", "root_cause_analysis", "remediation_plan", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v: Any) -> str:
        """Some models return these fields as arrays instead of strings. Join them."""
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return v

class QueryIntent(BaseModel):
    intent: Literal["Conversational","Coding"] = Field(..., description="The classified intent for the query")


class ImplementationPlan(BaseModel):
    """Structured plan for code implementation."""
    dependencies: List[str] = Field(
        default_factory=list,
        description="External packages needed (not in stdlib). Examples: numpy, requests, pandas"
    )
    logic_steps: List[str] = Field(
        description="High-level implementation steps in order"
    )
    complexity: Literal["simple", "moderate", "complex"] = Field(
        description="Estimated complexity level"
    )
    edge_cases: List[str] = Field(
        default_factory=list,
        description="Important edge cases to handle"
    )
    approach: str = Field(
        description="Brief description of recommended algorithm/approach"
    )
    