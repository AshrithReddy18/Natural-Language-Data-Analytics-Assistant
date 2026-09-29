"""Persistence for data sources, conversations, messages and query runs."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Conversation, DataSource, Message, QueryRun


class DataSourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def all(self) -> list[DataSource]:
        return list(self.db.scalars(select(DataSource).order_by(DataSource.is_demo.desc(), DataSource.created_at)))

    def get(self, source_id: str) -> DataSource | None:
        return self.db.get(DataSource, source_id)

    def get_demo(self) -> DataSource | None:
        return self.db.scalars(select(DataSource).where(DataSource.is_demo.is_(True))).first()

    def add(self, source: DataSource) -> DataSource:
        self.db.add(source)
        self.db.commit()
        return source

    def delete(self, source: DataSource) -> None:
        self.db.delete(source)
        self.db.commit()


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def with_message_counts(self, limit: int = 100) -> list[tuple[Conversation, int]]:
        counts = select(Message.conversation_id, func.count().label("n")).group_by(Message.conversation_id).subquery()
        stmt = (
            select(Conversation, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.conversation_id == Conversation.id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return [(c, int(n)) for c, n in self.db.execute(stmt).all()]

    def get(self, conversation_id: str, *, with_messages: bool = False) -> Conversation | None:
        if not with_messages:
            return self.db.get(Conversation, conversation_id)
        stmt = (
            select(Conversation).where(Conversation.id == conversation_id).options(selectinload(Conversation.messages))
        )
        return self.db.scalars(stmt).first()

    def create(self, *, title: str, data_source_id: str) -> Conversation:
        conversation = Conversation(title=title[:200], data_source_id=data_source_id)
        self.db.add(conversation)
        self.db.commit()
        return conversation

    def add_message(
        self,
        conversation: Conversation,
        *,
        role: str,
        content: str,
        payload: dict[str, Any] | None = None,
    ) -> Message:
        message = Message(conversation_id=conversation.id, role=role, content=content, payload=payload)
        conversation.updated_at = datetime.now(UTC)
        self.db.add(message)
        self.db.commit()
        return message

    def recent_messages(self, conversation_id: str, limit: int) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(self.db.scalars(stmt).all()))

    def delete(self, conversation: Conversation) -> None:
        self.db.execute(delete(QueryRun).where(QueryRun.conversation_id == conversation.id))
        self.db.delete(conversation)
        self.db.commit()


class QueryRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, run: QueryRun) -> QueryRun:
        self.db.add(run)
        self.db.commit()
        return run

    def recent(self, *, data_source_id: str | None = None, limit: int = 50) -> list[QueryRun]:
        stmt = select(QueryRun).order_by(QueryRun.created_at.desc()).limit(limit)
        if data_source_id:
            stmt = stmt.where(QueryRun.data_source_id == data_source_id)
        return list(self.db.scalars(stmt))
