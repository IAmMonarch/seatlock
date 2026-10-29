import uuid
from datetime import datetime
from typing import Annotated, Any, Self
from zoneinfo import available_timezones

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from seatlock.auth.schemas import NormalizedEmail
from seatlock.venues.models import VenueType

VALID_TIMEZONES = available_timezones()
MAX_SEATS_PER_VENUE = 100_000


def _strip(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _strip_upper(value: Any) -> Any:
    return value.strip().upper() if isinstance(value, str) else value


def _validate_timezone(tz_name: str) -> str:
    if tz_name not in VALID_TIMEZONES:
        raise ValueError(f"Unknown timezone: {tz_name}")
    return tz_name


CleanStr = Annotated[str, BeforeValidator(_strip)]
CleanUppercaseStr = Annotated[str, BeforeValidator(_strip_upper)]
TimezoneName = Annotated[str, AfterValidator(_validate_timezone)]


class ContactIn(BaseModel):
    name: CleanStr = Field(min_length=1, max_length=100)
    email: NormalizedEmail
    phone: CleanStr = Field(min_length=7, max_length=20)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str
    phone: str


class RowIn(BaseModel):
    label: CleanUppercaseStr = Field(min_length=1, max_length=5)
    seats: int = Field(gt=0, le=500)


class SectionIn(BaseModel):
    name: CleanStr = Field(min_length=1, max_length=100)
    rows: list[RowIn] = Field(min_length=1, max_length=500)

    @field_validator("rows")
    @classmethod
    def unique_row_label(cls, rows: list[RowIn]) -> list[RowIn]:
        labels = [r.label for r in rows]
        if len(labels) != len(set(labels)):
            raise ValueError("Row labels must be unique within a section")
        return rows


class VenueCreate(BaseModel):
    name: CleanStr = Field(min_length=1, max_length=100)
    address: CleanStr = Field(min_length=1, max_length=255)
    city: CleanStr = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    contact: ContactIn
    capacity: int = Field(gt=0)
    venue_type: VenueType
    timezone: TimezoneName

    sections: list[SectionIn] = Field(min_length=1, max_length=500)

    @field_validator("sections")
    @classmethod
    def unique_section_names(cls, sections: list[SectionIn]) -> list[SectionIn]:
        names = [s.name.lower() for s in sections]
        if len(names) != len(set(names)):
            raise ValueError("Section names must be unique within a venue")
        return sections

    @model_validator(mode="after")
    def check_seat_totals(self) -> Self:
        total_seats = sum(
            row.seats for section in self.sections for row in section.rows
        )
        if total_seats > MAX_SEATS_PER_VENUE:
            raise ValueError(f"A venue can have at most {MAX_SEATS_PER_VENUE} seats")
        if self.capacity > total_seats:
            raise ValueError(
                f"Capacity ({self.capacity}) is more than "
                f"the number of seats ({total_seats})"
            )
        return self


class VenueUpdate(BaseModel):
    """Partial update: only the fields the client sends are changed.

    Sections are managed through their own endpoints, and the
    capacity-vs-seats check happens in the service.
    """

    name: CleanStr | None = Field(default=None, min_length=1, max_length=100)
    address: CleanStr | None = Field(default=None, min_length=1, max_length=255)
    city: CleanStr | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    contact: ContactIn | None = None
    capacity: int | None = Field(default=None, gt=0)
    venue_type: VenueType | None = None
    timezone: TimezoneName | None = None

    @model_validator(mode="after")
    def no_null_for_required_fields(self) -> Self:
        # Leaving a field out is fine; sending it as null is not,
        # except for description, where null means "clear it".
        nullable = {"description"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class SeatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_label: str
    seat_number: int


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    address: str
    city: str
    description: str | None
    contact: ContactOut
    capacity: int
    venue_type: VenueType
    timezone: str
    sections: list[SectionOut]
    created_at: datetime
    updated_at: datetime
