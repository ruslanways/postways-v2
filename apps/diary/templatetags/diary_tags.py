"""
Django template tags and filters for the diary application.

This module provides custom template tags and filters for rendering
like indicators and modifying URL links in templates.

Best Practices:
    - For list views (multiple posts): Use the `has_liked` annotation on post
      objects instead of the `like_or_unlike` template tag to avoid N+1 query
      problems. Views annotate posts with `has_liked` (boolean) via subquery.

    - For single post views: Use `post.has_liked` annotation for consistency.

    - The `like_or_unlike` tag is available for edge cases where the annotation
      is not available, but should be avoided in loops.
"""

import os
import re

from django import template

from apps.diary.models import Like

register = template.Library()


@register.simple_tag
def like_or_unlike(user, post):
    """
    Return a heart symbol indicating whether the user has liked the post.

    Args:
        user: The user to check for a like (CustomUser instance)
        post: The post to check (Post instance)

    Returns:
        str: HTML entity for filled heart (❤) if liked, empty heart (♡) otherwise
    """
    is_liked = Like.objects.filter(user=user, post=post).exists()
    return "&#10084;" if is_liked else "&#9825;"


@register.filter
def filename(value):
    """
    Extract the filename from a file path.

    Args:
        value: A file path string or FieldFile object

    Returns:
        str: Just the filename without the directory path
    """
    if not value:
        return ""
    # Handle both string paths and FieldFile objects
    path = str(value)
    return os.path.basename(path)


@register.filter(is_safe=True)
def url_target_blank(text):
    """
    Add target="_blank" to all anchor tags in the text.

    This filter ensures all links open in a new tab. If a link already
    has a target attribute, it will be preserved (not duplicated).

    Args:
        text: HTML string containing anchor tags

    Returns:
        str: HTML string with target="_blank" added to all anchor tags
    """
    if not text:
        return text

    # Pattern to match <a> tags that don't already have target attribute
    # Uses negative lookahead to avoid adding duplicate target attributes
    # Matches <a followed by optional whitespace, but only if target= doesn't exist
    pattern = r"<a(\s*)(?![^>]*\starget\s*=)"

    def replacer(match):
        """Add target="_blank" with proper spacing."""
        whitespace = match.group(1) or " "  # Use existing whitespace or add a space
        return f'<a{whitespace}target="_blank" '

    return re.sub(pattern, replacer, text)
