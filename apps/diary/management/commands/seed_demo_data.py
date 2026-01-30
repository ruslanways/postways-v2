"""
Seed demo data for showcasing the Postways application.

This management command populates the database with realistic-looking fake data
including users, posts, and likes. Useful for demos, testing, and development.

Usage:
    # Basic usage with defaults (10 users, 50 posts, up to 20 likes per post)
    python manage.py seed_demo_data

    # Custom counts
    python manage.py seed_demo_data --users=20 --posts=100 --max-likes=30

    # Include random images from picsum.photos
    python manage.py seed_demo_data --with-images

    # Clear existing data before seeding (preserves staff/superusers)
    python manage.py seed_demo_data --clear

    # Docker usage
    docker compose -f docker/docker-compose.yml exec web python manage.py seed_demo_data

Arguments:
    --users       Number of demo users to create (default: 10)
    --posts       Number of posts to create (default: 50)
    --max-likes   Maximum likes per post, randomly distributed (default: 20)
    --with-images Download random images from picsum.photos for each post
    --clear       Delete demo data only (posts/likes by non-staff users, then the users)

What gets created:
    - Users with unique usernames/emails (password: "demo12345"), joined 90-180 days ago
    - Posts with varied titles (4-8 words) and content (1-6 paragraphs)
    - Random images from picsum.photos with varied dimensions when --with-images is used
    - Post dates are always after their author's join date
    - Likes randomly distributed across posts from the created users

Notes:
    - Use --with-images to download random images (slower due to network requests).
    - The --clear flag only deletes data from non-staff/non-superuser accounts.
    - All operations run in a single database transaction (atomic).
"""

import random
import urllib.request
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from faker import Faker

from apps.diary.models import Like, Post

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Seed demo data for showcase"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=10)
        parser.add_argument("--posts", type=int, default=50)
        parser.add_argument("--max-likes", type=int, default=20)
        parser.add_argument(
            "--clear", action="store_true", help="Clear existing demo data first"
        )
        parser.add_argument(
            "--with-images",
            action="store_true",
            help="Download random images from picsum.photos for each post",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        users_count = options["users"]
        posts_count = options["posts"]
        max_likes = options["max_likes"]

        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            # Only delete data from non-staff/non-superuser accounts
            demo_users = User.objects.filter(is_staff=False, is_superuser=False)
            Like.objects.filter(user__in=demo_users).delete()
            Post.objects.filter(author__in=demo_users).delete()
            demo_users.delete()

        self.stdout.write("Creating users...")
        now = timezone.now()
        users = []
        used_usernames = set(User.objects.values_list("username", flat=True))
        for _ in range(users_count):
            username = fake.user_name()
            while username in used_usernames:
                username = fake.user_name()
            used_usernames.add(username)
            # Users joined 90-180 days ago (before any posts)
            date_joined = now - timedelta(
                days=random.randint(90, 180),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            user = User.objects.create_user(
                username=username,
                email=fake.email(),
                password="demo12345",
                date_joined=date_joined,
            )
            users.append(user)

        self.stdout.write("Creating posts...")
        with_images = options["with_images"]
        posts = []

        for i in range(posts_count):
            author = random.choice(users)
            # Post created between user's join date and now
            days_since_joined = (now - author.date_joined).days
            post_date = author.date_joined + timedelta(
                days=random.randint(0, days_since_joined),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            post = Post(
                author=author,
                title=fake.sentence(nb_words=random.randint(4, 8)).rstrip("."),
                content="\n\n".join(fake.paragraphs(random.randint(1, 6))),
            )

            if with_images:
                image_data = self._download_random_image()
                if image_data:
                    filename = f"demo_{fake.uuid4()}.jpg"
                    post.image.save(filename, ContentFile(image_data), save=False)
                if (i + 1) % 10 == 0:
                    self.stdout.write(
                        f"  Created {i + 1}/{posts_count} posts with images..."
                    )

            post.save()
            posts.append((post, post_date))

        # Assign creation/updated dates (post dates must be after author's join date)
        for post, post_date in posts:
            post.created_at = post_date
            post.updated_at = post_date
        Post.objects.bulk_update([p for p, _ in posts], ["created_at", "updated_at"])

        self.stdout.write("Creating likes...")
        likes_to_create = []
        for post, _ in posts:
            likers = random.sample(users, random.randint(0, min(len(users), max_likes)))
            for user in likers:
                likes_to_create.append(Like(user=user, post=post))

        Like.objects.bulk_create(likes_to_create, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS("Demo data created successfully"))

    def _download_random_image(self):
        """Download a random image from picsum.photos with varied dimensions."""
        # Various aspect ratios and sizes for visual variety
        dimensions = [
            (800, 600),  # 4:3 landscape
            (600, 800),  # 3:4 portrait
            (1000, 600),  # wide landscape
            (600, 400),  # small landscape
            (700, 700),  # square
            (900, 500),  # panoramic
            (500, 750),  # tall portrait
            (1200, 900),  # large landscape
            (3000, 2000),  # iPhone-like large
        ]
        width, height = random.choice(dimensions)
        try:
            url = f"https://picsum.photos/{width}/{height}"
            request = urllib.request.Request(
                url, headers={"User-Agent": "PostwaysSeeder/1.0"}
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.read()
        except Exception as e:
            self.stderr.write(f"Failed to download image: {e}")
            return None
