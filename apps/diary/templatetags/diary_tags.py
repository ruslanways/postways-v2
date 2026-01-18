from django import template
from apps.diary.models import Like

register = template.Library()


@register.simple_tag
def like_or_unlike(author, post):
    return (
        "&#10084;"
        if Like.objects.filter(user=author, post=post).exists()
        else "&#9825;"
    )


@register.filter(is_safe=True)
def url_target_blank(text):
    return text.replace("<a ", '<a target="_blank" ')
