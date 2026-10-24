import dataclasses
import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, composite, mapped_column, relationship

from seatlock.database import Base

if TYPE_CHECKING:
    from seatlock.events.models import Event


class VenueType(enum.StrEnum):
    HOTEL = "hotel"
    STADIUM = "stadium"
    BANQUET = "banquet"
    HALL = "hall"
    GARDEN = "garden"
    CLUB = "club"


@dataclasses.dataclass
class Contact:
    name: str
    email: str
    phone: str


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (CheckConstraint("capacity > 0", name="capacity_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    contact: Mapped[Contact] = composite(
        mapped_column("contact_name", String(100)),
        mapped_column("contact_email", String(255)),
        mapped_column("contact_phone", String(20)),
    )

    capacity: Mapped[int]

    events: Mapped[list["Event"]] = relationship(
        back_populates="venue", passive_deletes="all"
    )
    sections: Mapped[list["Section"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan", passive_deletes=True
    )

    venue_type: Mapped[VenueType] = mapped_column(
        Enum(
            VenueType,
            native_enum=False,
            length=100,
            values_callable=lambda x: [i.value for i in x],
        )
    )

    timezone: Mapped[str] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("venue_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))

    seats: Mapped[list["Seat"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", passive_deletes=True
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE")
    )

    venue: Mapped[Venue] = relationship(back_populates="sections")


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("section_id", "row_label", "seat_number"),
        CheckConstraint("seat_number > 0", name="seat_number_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    row_label: Mapped[str] = mapped_column(String(5))
    seat_number: Mapped[int]

    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE")
    )

    section: Mapped[Section] = relationship(back_populates="seats")
