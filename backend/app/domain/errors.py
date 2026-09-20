"""Stable business-error codes for future gated adapters to translate."""


class DomainError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def require_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainError("INVALID_ARGUMENT", f"{field} must be a nonempty string.")


def require_identifier(value: object, field: str) -> None:
    require_text(value, field)
    if value != value.strip():
        raise DomainError("INVALID_ARGUMENT", f"{field} must not contain surrounding whitespace.")


def require_money(value: object, field: str, *, allow_zero: bool = False) -> None:
    # bool is an int subclass; exact typing avoids treating True as one rupee.
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        qualifier = "nonnegative" if allow_zero else "positive"
        raise DomainError("INVALID_ARGUMENT", f"{field} must be a {qualifier} whole-rupee integer.")
