from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task
from .models import CustomUser, Post, Like


@shared_task()
def send_email_task(link_to_change_user, token, user_email):
    """Sends an email when the feedback form has been submitted."""
    send_mail(
            "Postways token recovery",
            f"Here are your new access token expires in 5 min."
            f"\n\n'access': {token}\n\n"
            "You can use it to change password by Post-request to: "
            f"{link_to_change_user}"
            "\n\nTherefore you could obtain new tokens pair by logging.",
            None,
            [user_email],
        )


@shared_task()
def send_week_report():

    now = timezone.now()
    week_ago = datetime.now()-timedelta(days=7)
    users = CustomUser.objects.filter(date_joined__range=(week_ago, now)).count()
    posts = Post.objects.filter(created__range=(week_ago, now)).count()
    likes = Like.objects.filter(created__range=(week_ago, now)).count()

    send_mail(
        "Postways week report",
        "Hi admin."
        "\n\nFor the last week 'Postways' got\n\n"
        f"new users: {users}\n"
        f"new posts: {posts}\n"
        f"new likes: {likes}\n"
        "\nHave a nice weekend😉",
        None,
        settings.WEEKLY_REPORT_RECIPIENTS
    )
