from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.session import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get(self, record_id: str) -> ModelT | None:
        return self.session.get(self.model, record_id)

    def require(self, record_id: str) -> ModelT:
        record = self.get(record_id)
        if record is None:
            raise LookupError(f"{self.model.__name__} {record_id!r} was not found.")
        return record

    def list(self, *, offset: int = 0, limit: int = 100) -> Sequence[ModelT]:
        statement = select(self.model).offset(offset).limit(limit)
        return self.session.scalars(statement).all()

    def count(self, statement: Select[Any] | None = None) -> int:
        if statement is None:
            statement = select(func.count()).select_from(self.model)
        value = self.session.scalar(statement)
        return int(value or 0)

    def add(self, record: ModelT, *, commit: bool = True) -> ModelT:
        self.session.add(record)
        if commit:
            self.session.commit()
            self.session.refresh(record)
        return record

    def delete(self, record: ModelT, *, commit: bool = True) -> None:
        self.session.delete(record)
        if commit:
            self.session.commit()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
