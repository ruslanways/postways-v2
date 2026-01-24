"""
Validators for the diary application.

This module provides custom validators for username validation and content
profanity checking.
"""

import string
from pathlib import Path
from typing import Any

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class MyUnicodeUsernameValidator(UnicodeUsernameValidator):
    """
    Custom username validator extending Django's UnicodeUsernameValidator.

    Allows letters, numbers, and @ . + - _ characters in usernames.
    """

    message = _(
        "Enter a valid username. This value may contain only letters, "
        "numbers, and @ . + - _ characters."
    )


# bad-words.txt should be a plain text file with profanity words separated by
# whitespace (typically one word per line). No punctuation or comments.
BAD_WORDS_PATH = Path(__file__).resolve().parent / "profanity/bad-words.txt"

try:
    BAD_WORDS = set(BAD_WORDS_PATH.read_text(encoding="utf-8").split())
except FileNotFoundError:
    # If the file doesn't exist, use an empty set (no profanity filtering)
    # This allows the app to run even if the file is missing
    BAD_WORDS = set()


def profanity(content: Any) -> None:
    """
    Validate that content does not contain profanity.

    Checks content against a word list by:
    1. Converting to lowercase
    2. Splitting into words
    3. Stripping punctuation from each word
    4. Comparing against the bad words set

    Args:
        content: The content string to validate

    Raises:
        ValidationError: If profanity is detected, with details about
                        which words were found
    """
    if not isinstance(content, str):
        return  # Skip validation for non-string content

    # Simple word-list check: split on whitespace and strip punctuation.
    tokens = [word.strip(string.punctuation) for word in content.casefold().split()]
    profanity_check = BAD_WORDS & set(tokens)
    if profanity_check:
        raise ValidationError(
            _("Using profanity (%(words)s) is prohibited. Please correct the content."),
            code="invalid",
            params={"words": ", ".join(sorted(profanity_check))},
        )
