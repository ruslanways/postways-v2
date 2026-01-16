from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import string
from pathlib import Path


class MyUnicodeUsernameValidator(UnicodeUsernameValidator):
    message = _(
        "Enter a valid username. This value may contain only letters, "
        "numbers, and @ . + - _ characters."
    )

# bad-words.txt should be a plain text file with profanity words separated by
# whitespace (typically one word per line). No punctuation or comments.
BAD_WORDS_PATH = Path(__file__).resolve().parent / "profanity/bad-words.txt"
BAD_WORDS = set(BAD_WORDS_PATH.read_text(encoding="utf-8").split())


def profanity(content):
    # Simple word-list check: split on whitespace and strip punctuation.
    tokens = [word.strip(string.punctuation) for word in content.casefold().split()]
    profanity_check = BAD_WORDS & set(tokens)
    if profanity_check:
        raise ValidationError(
            _(
                "Using profanity (%(words)s) is prohibited. Please correct the content."
            ),
            code='invalid',
            params={"words": ", ".join(sorted(profanity_check))},
        )
