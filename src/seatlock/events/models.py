import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from seatlock.database import Base
from seatlock.venues.models import Venue


class EventStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EventSeatStatus(enum.StrEnum):
    AVAILABLE = "available"
    HELD = "held"
    SOLD = "sold"


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="start_before_end"),
        CheckConstraint(
            "status IN ('draft', 'published', 'completed', 'cancelled')",
            name="status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="RESTRICT"), index=True
    )
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    title: Mapped[str] = mapped_column(String(100))
    venue: Mapped[Venue] = relationship(back_populates="events")
    status: Mapped[EventStatus] = mapped_column(
        Enum(
            EventStatus,
            native_enum=False,
            length=20,
            values_callable=lambda x: [i.value for i in x],
        ),
        default=EventStatus.DRAFT,
        server_default=EventStatus.DRAFT.value,
    )

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EventSeat(Base):
    __tablename__ = "event_seats"
    __table_args__ = (
        UniqueConstraint("event_id", "seat_id"),
        CheckConstraint("price >= 0", name="price_not_negative"),
        CheckConstraint("status IN ('available', 'held', 'sold')", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    seat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seats.id", ondelete="RESTRICT"), index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="RESTRICT")
    )

    price: Mapped[int]
    status: Mapped[EventSeatStatus] = mapped_column(
        Enum(
            EventSeatStatus,
            native_enum=False,
            length=20,
            values_callable=lambda x: [i.value for i in x],
        ),
        default=EventSeatStatus.AVAILABLE,
        server_default=EventSeatStatus.AVAILABLE.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
