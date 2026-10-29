import uuid

from fastapi import APIRouter, HTTPException, status

from seatlock.auth.dependencies import Organizer
from seatlock.dependencies import DbSession
from seatlock.venues.exceptions import (
    CapacityExceedsSeatsError,
    SeatsInUseError,
    SectionNameTakenError,
    SectionNotFoundError,
    VenueNotFoundError,
)
from seatlock.venues.models import Section, Venue
from seatlock.venues.schemas import (
    SectionIn,
    SectionOut,
    VenueCreate,
    VenueOut,
    VenueUpdate,
)
from seatlock.venues.service import (
    s_create_venue,
    s_get_owner_venues,
    s_update_section,
    s_update_venue,
)

router = APIRouter(prefix="/venues", tags=["venues"])


@router.post("/create", response_model=VenueOut, status_code=status.HTTP_201_CREATED)
async def create_venue(data: VenueCreate, db: DbSession, user: Organizer) -> Venue:
    return await s_create_venue(db, user.id, data)


@router.get("/mine", response_model=list[VenueOut])
async def list_my_venues(db: DbSession, user: Organizer) -> list[Venue]:
    return await s_get_owner_venues(db, user.id)


@router.patch("/update/{venue_id}", response_model=VenueOut)
async def update_venue(
    venue_id: uuid.UUID, data: VenueUpdate, db: DbSession, user: Organizer
) -> Venue:
    try:
        return await s_update_venue(db, venue_id, user, data)
    except VenueNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found"
        ) from None
    except CapacityExceedsSeatsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from None


# Replace a section's name and full row layout
@router.put("/{venue_id}/sections/{section_id}", response_model=SectionOut)
async def update_section(
    venue_id: uuid.UUID,
    section_id: uuid.UUID,
    data: SectionIn,
    db: DbSession,
    user: Organizer,
) -> Section:
    try:
        return await s_update_section(db, venue_id, section_id, data, user)
    except SectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Section not found"
        ) from None
    except SectionNameTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Section name is in use"
        ) from None
    except SeatsInUseError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Some seats are used by events and can't be removed",
        ) from None
    except CapacityExceedsSeatsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from None
