import uuid

from sqlalchemy import and_, case, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from seatlock.auth.models import User, UserRole
from seatlock.events.models import EventSeat
from seatlock.venues.exceptions import (
    CapacityExceedsSeatsError,
    SeatsInUseError,
    SectionNameTakenError,
    SectionNotFoundError,
    VenueNotFoundError,
)
from seatlock.venues.models import Contact, Seat, Section, Venue
from seatlock.venues.schemas import SectionIn, VenueCreate, VenueUpdate


async def s_create_venue(
    db: AsyncSession, owner_id: uuid.UUID, data: VenueCreate
) -> Venue:
    venue = Venue(
        name=data.name,
        owner_id=owner_id,
        address=data.address,
        city=data.city,
        description=data.description,
        contact=Contact(**data.contact.model_dump()),
        capacity=data.capacity,
        venue_type=data.venue_type,
        timezone=data.timezone,
        sections=[
            Section(
                name=s.name,
                seats=[
                    Seat(row_label=row.label, seat_number=n)
                    for row in s.rows
                    for n in range(1, row.seats + 1)
                ],
            )
            for s in data.sections
        ],
    )

    db.add(venue)
    await db.commit()

    await db.refresh(venue, ["created_at", "updated_at"])
    return venue


async def s_get_owner_venues(db: AsyncSession, owner_id: uuid.UUID) -> list[Venue]:
    result = await db.scalars(
        select(Venue)
        .where(Venue.owner_id == owner_id)
        .options(selectinload(Venue.sections))
        .order_by(Venue.created_at.desc())
    )

    return list(result.all())


async def s_update_venue(
    db: AsyncSession, venue_id: uuid.UUID, user: User, data: VenueUpdate
) -> Venue:
    venue = await db.scalar(
        select(Venue).where(Venue.id == venue_id).options(selectinload(Venue.sections))
    )
    if venue is None or (venue.owner_id != user.id and user.role != UserRole.ADMIN):
        raise VenueNotFoundError

    changes = data.model_dump(exclude_unset=True)

    if "capacity" in changes:
        total_seats = (
            await db.scalar(
                select(func.count(Seat.id))
                .join(Section)
                .where(Section.venue_id == venue.id)
            )
            or 0
        )
        if changes["capacity"] > total_seats:
            raise CapacityExceedsSeatsError(changes["capacity"], total_seats)

    if "contact" in changes:
        changes["contact"] = Contact(**changes["contact"])

    for field, value in changes.items():
        setattr(venue, field, value)

    await db.commit()
    await db.refresh(venue, ["updated_at"])
    return venue


async def s_update_section(
    db: AsyncSession,
    venue_id: uuid.UUID,
    section_id: uuid.UUID,
    data: SectionIn,
    user: User,
) -> Section:
    section = await db.scalar(
        select(Section)
        .where(Section.id == section_id, Section.venue_id == venue_id)
        .options(joinedload(Section.venue))
    )
    if section is None or (
        section.venue.owner_id != user.id and user.role != UserRole.ADMIN
    ):
        raise SectionNotFoundError

    if data.name != section.name:
        taken = await db.scalar(
            select(Section.id).where(
                Section.venue_id == venue_id, Section.name == data.name
            )
        )
        if taken:
            raise SectionNameTakenError

    row_counts = {row.label: row.seats for row in data.rows}

    removed = and_(
        Seat.section_id == section_id,
        or_(
            Seat.row_label.not_in(list(row_counts)),
            Seat.seat_number > case(row_counts, value=Seat.row_label),
        ),
    )

    in_use = await db.scalar(
        select(EventSeat.seat_id)
        .join(Seat, Seat.id == EventSeat.seat_id)
        .where(removed)
        .limit(1)
    )
    if in_use:
        raise SeatsInUseError

    other_seats = (
        await db.scalar(
            select(func.count(Seat.id))
            .join(Section)
            .where(Section.venue_id == venue_id, Section.id != section_id)
        )
        or 0
    )
    total_seats = other_seats + sum(row_counts.values())
    if section.venue.capacity > total_seats:
        raise CapacityExceedsSeatsError(section.venue.capacity, total_seats)

    current_max = dict(
        (
            await db.execute(
                select(Seat.row_label, func.max(Seat.seat_number))
                .where(Seat.section_id == section_id)
                .group_by(Seat.row_label)
            )
        )
        .tuples()
        .all()
    )

    new_seats = [
        {"section_id": section_id, "row_label": label, "seat_number": n}
        for label, count in row_counts.items()
        for n in range(current_max.get(label, 0) + 1, count + 1)
    ]

    section.name = data.name
    await db.execute(delete(Seat).where(removed))
    if new_seats:
        await db.execute(insert(Seat), new_seats)
    await db.commit()
    return section
