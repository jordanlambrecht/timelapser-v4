from enum import Enum
from typing import List, Optional, Type


def parse_enum(
    enum_cls: Type[Enum],
    value: str,
    valid_members: Optional[List[Enum]] = None,
    default: Optional[Enum] = None,
) -> Enum:
    """
    Convert a string to an enum member, with optional valid member filtering and default fallback.

    Args:
        enum_cls (Type[Enum]): The enum class to parse against.
        value (str): The string value to match to an enum member's .value.
        valid_members (Optional[List[Enum]]): Optional list of enum members to restrict valid choices (e.g., excluding UNKNOWN).
        default (Optional[Enum]): Enum member to return if no match is found. If not provided, returns the first valid member.

    Returns:
        Enum: The matching enum member, or the default/fallback member.

    Example:
        >>> from app.enums import VideoAutomationMode
        >>> parse_enum(VideoAutomationMode, "manual")
        <VideoAutomationMode.MANUAL: 'manual'>

        >>> parse_enum(VideoAutomationMode, "invalid", default=VideoAutomationMode.MANUAL)
        <VideoAutomationMode.MANUAL: 'manual'>

        >>> parse_enum(VideoAutomationMode, "scheduled", valid_members=VideoAutomationMode.get_valid_modes())
        <VideoAutomationMode.SCHEDULED: 'scheduled'>

    This helper is useful for converting user input, API parameters, or config values to enum members,
    and for enforcing business logic by restricting valid members and providing a safe fallback.
    """
    if valid_members is None:
        valid_members = list(enum_cls)
    for member in valid_members:
        if member.value == value:
            return member
    return default if default is not None else valid_members[0]
