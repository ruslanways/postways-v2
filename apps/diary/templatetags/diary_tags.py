"""
Django template tags and filters for the diary application.

This module provides custom template tags and filters for rendering
like indicators and modifying URL links in templates.

Best Practices:
    - For list views (multiple posts): Use the `liked_by_user` set from context
      instead of the `like_or_unlike` template tag to avoid N+1 query problems.
      The views provide this set via bulk queries for efficiency.
    
    - For single post views: Either approach works, but using `liked_by_user` set
      is preferred for consistency and performance.
    
    - The `like_or_unlike` tag is available for edge cases where the set is not
      provided, but should be avoided in loops.
"""
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
    pattern = r'<a(\s*)(?![^>]*\starget\s*=)'
    
    def replacer(match):
        """Add target="_blank" with proper spacing."""
        whitespace = match.group(1) or ' '  # Use existing whitespace or add a space
        return f'<a{whitespace}target="_blank" '
    
    return re.sub(pattern, replacer, text)
