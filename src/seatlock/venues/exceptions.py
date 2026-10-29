class VenueNotFoundError(Exception):
    pass


class CapacityExceedsSeatsError(Exception):
    def __init__(self, capacity: int, total_seats: int) -> None:
        super().__init__(
            f"Capacity ({capacity}) is more than the number of seats ({total_seats})"
        )


class SectionNotFoundError(Exception):
    pass


class SectionNameTakenError(Exception):
    pass


class SeatsInUseError(Exception):
    pass
