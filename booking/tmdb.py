import requests
from django.conf import settings
from booking.models import Movie

def fetch_latest_movies(language_code="hi"):
    """
    Fetch latest movies from TMDb by original language.
    Example: language_code="hi" for Hindi, "en" for English.
    """
    api_key = getattr(settings, "TMDB_API_KEY", None)
    if not api_key:
        return []

    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": api_key,
        "with_original_language": language_code,
        "sort_by": "release_date.desc",
        "page": 1
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json().get("results", [])
    except Exception as e:
        print("TMDB FETCH ERROR:", e)
        return []
    
    language_map = {
    "hi": "Hindi",
    "en": "English",
    "ta": "Tamil",
    "te": "Telugu",
}
    movies = []
    for m in data:
        movie, _ = Movie.objects.update_or_create(
            tmdb_id=m["id"],
            defaults={
            "title": m.get("title") or "",
            "overview": m.get("overview") or "",
            "poster_path": m.get("poster_path") or "",
            "release_date": m.get("release_date") or None,
            "language": language_map.get(language_code, language_code),
            "is_active": True,
            "rating": m.get("vote_average") or 0,
            "vote_count": m.get("vote_count") or 0,
}
        )
        movies.append(movie)
    return movies
