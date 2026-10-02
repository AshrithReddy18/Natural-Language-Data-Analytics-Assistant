"""Conversation handling: context building, running the pipeline, and persisting the outcome."""

import logging
import time
from typing import Literal, cast

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import LLMNotConfiguredError, NotFoundError
from app.core.logging import log_event
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.models.entities import Conversation, Message, QueryRun, User
from app.repositories.repositories import ConversationRepository, QueryRunRepository
from app.schemas.analysis import AnalysisResult, QueryResultData
from app.schemas.api import ChatResponse, ConversationDetail, ConversationSummary, MessageOut
from app.services.analysis_pipeline import AnalysisPipeline, Emit
from app.services.datasource_service import DataSourceService, connector_for
from app.services.text_to_sql import PriorTurn

logger = logging.getLogger(__name__)

# Bounded preview stored with each message so a past analysis can be reopened without re-running
# its query. Full result sets are never persisted.
STORED_PREVIEW_ROWS = 500
CONTEXT_SAMPLE_ROWS = 5


def message_out(message: Message) -> MessageOut:
    analysis = AnalysisResult.model_validate(message.payload) if message.payload else None
    return MessageOut(
        id=message.id,
        role=cast(Literal["user", "assistant"], message.role),
        content=message.content,
        created_at=message.created_at,
        analysis=analysis,
    )


def build_history(messages: list[Message], max_turns: int) -> list[PriorTurn]:
    """Summarise the last `max_turns` question/answer pairs. Older turns are dropped: follow-ups
    almost always refer to recent results, and this keeps prompts small and predictable."""
    turns: list[PriorTurn] = []
    pending_question: str | None = None
    for message in messages:
        if message.role == "user":
            pending_question = message.content
            continue
        if pending_question is None:
            continue
        analysis = AnalysisResult.model_validate(message.payload) if message.payload else None
        turn = PriorTurn(question=pending_question)
        if analysis:
            turn.interpretation = analysis.interpretation
            if analysis.sql and analysis.sql.validated_sql and analysis.status in ("success", "empty"):
                turn.sql = analysis.sql.validated_sql
            if analysis.result:
                turn.columns = [c.name for c in analysis.result.columns]
                turn.row_count = analysis.result.row_count
                turn.sample_rows = analysis.result.rows[:CONTEXT_SAMPLE_ROWS]
            if analysis.status == "clarification" and analysis.clarification:
                turn.note = f"I asked for clarification: {analysis.clarification.question}"
            elif analysis.status == "error" and analysis.error:
                turn.note = f"This attempt failed: {analysis.error.message}"
        turns.append(turn)
        pending_question = None
    return turns[-max_turns:] if max_turns else []


def _title_from(question: str) -> str:
    title = " ".join(question.split())
    return title if len(title) <= 60 else title[:57].rstrip() + "…"


def _stored_payload(result: AnalysisResult) -> dict:
    stored = result.model_copy(deep=True)
    if stored.result and stored.result.row_count > STORED_PREVIEW_ROWS:
        stored.result = QueryResultData(
            **{**stored.result.model_dump(), "rows": stored.result.rows[:STORED_PREVIEW_ROWS]}
        )
    return stored.model_dump(mode="json")


def _assistant_text(result: AnalysisResult) -> str:
    if result.status == "clarification" and result.clarification:
        return result.clarification.question
    if result.status == "error" and result.error:
        return result.error.message
    if result.status == "empty":
        return "No records matched the requested criteria."
    if result.insight:
        return result.insight.headline
    return result.interpretation or ""


class ChatService:
    def __init__(self, db: Session, user: User, provider: LLMProvider | None = None) -> None:
        self.db = db
        self.user = user
        self.conversations = ConversationRepository(db)
        self.runs = QueryRunRepository(db)
        self.sources = DataSourceService(db, user)
        self._provider = provider

    def _own_conversation(self, conversation_id: str, *, with_messages: bool = False) -> Conversation:
        conversation = self.conversations.get(conversation_id, with_messages=with_messages)
        if conversation is None or conversation.owner_id != self.user.id:
            raise NotFoundError("Conversation not found.")
        return conversation

    def _resolve_provider(self) -> LLMProvider | None:
        if self._provider is not None:
            return self._provider
        try:
            return get_llm_provider()
        except LLMNotConfiguredError:
            return None

    def ask(
        self, *, question: str, data_source_id: str, conversation_id: str | None, emit: Emit | None = None
    ) -> ChatResponse:
        settings = get_settings()
        source = self.sources.get(data_source_id)
        if conversation_id:
            conversation = self._own_conversation(conversation_id)
            # Follow-ups always run against the conversation's own database: its history (SQL,
            # columns) only makes sense there.
            if conversation.data_source_id != source.id:
                source = self.sources.get(conversation.data_source_id)
        else:
            conversation = self.conversations.create(
                title=_title_from(question), data_source_id=source.id, owner_id=self.user.id
            )
        if emit:
            emit({"type": "conversation", "conversation_id": conversation.id, "title": conversation.title})

        prior = self.conversations.recent_messages(conversation.id, limit=settings.context_turns * 2)
        history = build_history(prior, settings.context_turns)
        user_message = self.conversations.add_message(conversation, role="user", content=question)

        started = time.perf_counter()
        pipeline = AnalysisPipeline(
            settings=settings,
            source_id=source.id,
            connector=connector_for(source),
            provider=self._resolve_provider(),
            business_notes=source.business_notes,
            currency=source.currency,
            emit=emit,
        )
        result = pipeline.run(question, history)

        run = self._record_run(result, source_id=source.id, conversation=conversation, source="chat")
        result.query_run_id = run.id if run else None
        assistant = self.conversations.add_message(
            conversation, role="assistant", content=_assistant_text(result), payload=_stored_payload(result)
        )
        if run:
            run.message_id = assistant.id
            self.db.commit()
        log_event(
            logger,
            "chat_answered",
            conversation_id=conversation.id,
            data_source_id=source.id,
            status=result.status,
            total_ms=int((time.perf_counter() - started) * 1000),
            row_count=result.result.row_count if result.result else None,
        )
        return ChatResponse(
            conversation_id=conversation.id,
            user_message=message_out(user_message),
            assistant_message=message_out(assistant),
        )

    def _record_run(
        self, result: AnalysisResult, *, source_id: str, conversation: Conversation | None, source: str
    ) -> QueryRun | None:
        if result.sql is None and result.status not in ("error",):
            return None  # clarifications / unanswerable: no query was produced
        status = {"success": "success", "empty": "success"}.get(result.status, "failed")
        if result.error and result.error.code == "query_timeout":
            status = "timeout"
        run = QueryRun(
            owner_id=self.user.id,
            data_source_id=source_id,
            conversation_id=conversation.id if conversation else None,
            source=source,
            question=result.question,
            generated_sql=result.sql.generated_sql if result.sql else None,
            validated_sql=result.sql.validated_sql if result.sql else None,
            status=status,
            error_message=result.error.message if result.error else None,
            row_count=result.result.row_count if result.result else None,
            execution_ms=result.result.execution_ms if result.result else None,
            attempts=max(1, len(result.sql.attempts)) if result.sql else 1,
        )
        return self.runs.add(run)

    # -- conversation queries --------------------------------------------------------------

    def list_conversations(self) -> list[ConversationSummary]:
        return [
            ConversationSummary(
                id=c.id,
                title=c.title,
                data_source_id=c.data_source_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=n,
            )
            for c, n in self.conversations.with_message_counts(self.user.id)
        ]

    def get_conversation(self, conversation_id: str) -> ConversationDetail:
        c = self._own_conversation(conversation_id, with_messages=True)
        return ConversationDetail(
            id=c.id,
            title=c.title,
            data_source_id=c.data_source_id,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=len(c.messages),
            messages=[message_out(m) for m in c.messages],
        )

    def delete_conversation(self, conversation_id: str) -> None:
        self.conversations.delete(self._own_conversation(conversation_id))
