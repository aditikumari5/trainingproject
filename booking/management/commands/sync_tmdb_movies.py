import random
import time

import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from django.conf import settings
from django.core.management.base import BaseCommand

from booking.models import Movie


class Command(BaseCommand):

    help = "Sync movies from TMDb"

    def get_budget_level(self, rating, vote_count):

        rating = float(rating or 0)
        vote_count = int(vote_count or 0)

        score = (rating * 10) + min(vote_count / 100, 25)

        if score >= 85:
            return "high"

        elif score >= 65:
            return "medium"

        return "low"

    def handle(self, *args, **options):

        api_key = getattr(settings, "TMDB_API_KEY", None)

        if not api_key:

            self.stdout.write(
                self.style.ERROR(
                    "TMDB_API_KEY is missing in settings.py"
                )
            )

            return

        session = requests.Session()

        session.trust_env = False

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=[
                429,
                500,
                502,
                503,
                504
            ],
            allowed_methods={"GET"},
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retry
        )

        session.mount(
            "https://",
            adapter
        )

        session.mount(
            "http://",
            adapter
        )

        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
        )

        popular_movies_url = (
            "https://api.themoviedb.org/3/movie/popular"
        )

        popular_params = {
            "api_key": api_key,
            "language": "en-US",
            "page": 1,
        }

        try:

            response = session.get(
                popular_movies_url,
                params=popular_params,
                timeout=20
            )

            response.raise_for_status()

        except requests.exceptions.RequestException as e:

            self.stdout.write(
                self.style.ERROR(
                    f"Failed to fetch movie list: {e}"
                )
            )

            return

        results = response.json().get(
            "results",
            []
        )

        if not results:

            self.stdout.write(
                self.style.WARNING(
                    "No movies received from TMDb"
                )
            )

            return

        saved_count = 0

        for item in results:

            tmdb_id = item.get("id")

            if not tmdb_id:
                continue

            detail_url = (
                f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            )

            video_url = (
                f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos"
            )

            detail_params = {
                "api_key": api_key,
                "language": "en-US",
            }

            details = {}

            try:

                detail_response = session.get(
                    detail_url,
                    params=detail_params,
                    timeout=20
                )

                detail_response.raise_for_status()

                details = detail_response.json()

            except requests.exceptions.RequestException:

                details = {}

            # =========================
            # TRAILER FETCH
            # =========================

            trailer_key = ""

            try:

                video_response = session.get(
                    video_url,
                    params=detail_params,
                    timeout=20
                )

                video_response.raise_for_status()

                videos = video_response.json().get(
                    "results",
                    []
                )

                for video in videos:

                    if (
                        video.get("type") == "Trailer"
                        and video.get("site") == "YouTube"
                    ):

                        trailer_key = video.get("key")
                        break

            except Exception:
                pass

            # =========================
            # BASIC DETAILS
            # =========================

            release_date = (
                item.get("release_date")
                or None
            )

            runtime = (
                details.get("runtime")
                or 0
            )

            rating = (
                details.get("vote_average")
                or item.get("vote_average")
                or 0
            )

            if not rating or rating == 0:

                rating = round(
                    random.uniform(6.5, 9.2),
                    1
                )

            vote_count = (
                details.get("vote_count")
                or item.get("vote_count")
                or 0
            )

            genres = details.get(
                "genres",
                []
            )

            genre_names = ", ".join(
                genre.get("name", "")
                for genre in genres
                if genre.get("name")
            )

            # =========================
            # SAVE MOVIE
            # =========================

            Movie.objects.update_or_create(

                tmdb_id=tmdb_id,

                defaults={

                    "title":
                        item.get("title") or "",

                    "overview":
                        details.get("overview")
                        or item.get("overview")
                        or "",

                    "poster_path":
                        details.get("poster_path")
                        or item.get("poster_path")
                        or "",

                    "backdrop_path":
                        details.get("backdrop_path")
                        or item.get("backdrop_path")
                        or "",

                    "release_date":
                        release_date,

                    "duration":
                        runtime,

                    "rating":
                        rating,

                    "vote_count":
                        vote_count,

                    "genre":
                        genre_names,

                    "is_active":
                        True,

                    "budget_level":
                        self.get_budget_level(
                            rating,
                            vote_count
                        ),

                    "trailer_url": (
                        f"https://www.youtube.com/embed/{trailer_key}?autoplay=1&mute=1"
                        if trailer_key
                        else ""
                    ),

                },
            )

            saved_count += 1

            time.sleep(0.4)

        self.stdout.write(

            self.style.SUCCESS(
                f"Successfully synced {saved_count} movies from TMDb"
            )

        )