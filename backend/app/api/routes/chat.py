import json
import logging
import queue
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.errors import AppError
from app.core.logging import request_id_var
from app.models.database import get_session_factory
from app.schemas.api import ChatRequest, ChatResponse, ConversationDetail, ConversationSummary
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

_DONE = object()


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Ask a question and wait for the complete answer."""
    return ChatService(db).ask(
        question=body.question, data_source_id=body.data_source_id, conversation_id=body.conversation_id
    )


@router.post("/chat/stream")
def chat_stream(body: ChatRequest) -> StreamingResponse:
    """Ask a question and receive newline-delimited JSON events as each pipeline step runs:

    {"type": "conversation", ...} → {"type": "step", "step": "generate", "status": "running"} ...
    → {"type": "result", "data": ChatResponse} | {"type": "error", "code", "message"}
    """
    events: queue.Queue[Any] = queue.Queue()
    request_id = request_id_var.get()

    def worker() -> None:
        request_id_var.set(request_id)
        db = get_session_factory()()
        try:
            response = ChatService(db).ask(
                question=body.question,
                data_source_id=body.data_source_id,
                conversation_id=body.conversation_id,
                emit=events.put,
            )
            events.put({"type": "result", "data": response.model_dump(mode="json")})
        except AppError as exc:
            events.put({"type": "error", "code": exc.code, "message": exc.message})
        except Exception:
            logger.exception("chat_stream_failed")
            events.put({"type": "error", "code": "internal_error", "message": "Something went wrong."})
        finally:
            db.close()
            events.put(_DONE)

    threading.Thread(target=worker, daemon=True).start()

    def stream() -> Iterator[str]:
        while (event := events.get()) is not _DONE:
            yield json.dumps(event, default=str) + "\n"

    return StreamingResponse(
        stream(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db)) -> list[ConversationSummary]:
    return ChatService(db).list_conversations()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ConversationDetail:
    return ChatService(db).get_conversation(conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)) -> Response:
    ChatService(db).delete_conversation(conversation_id)
    return Response(status_code=204)
