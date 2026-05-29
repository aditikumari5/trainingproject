import hashlib
import hmac
import io
import json
import random
import re
from datetime import datetime, timedelta
from decimal import Decimal
import qrcode
import razorpay
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import EmailMessage, send_mail
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from .models import (
    Booking,
    ContinueWatching,
    FoodCartItem,
    FoodItem,
    Movie,
    Seat,
    Show,
    Wishlist,
)

from django.http import HttpResponse
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
import razorpay
from django.db import transaction
from django.shortcuts import render, get_object_or_404
from django.shortcuts import render
from .models import Event
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError







BOOKING_HAS_USER_FIELD = any(f.name == "user" for f in Booking._meta.get_fields())
MOVIE_HAS_BUDGET_FIELD = any(f.name == "budget_level" for f in Movie._meta.get_fields())


# ---------------------------
# HELPERS
# ---------------------------

def ensure_seats_for_show(show):
    if Seat.objects.filter(show=show).exists():
        return

    for row in ["A", "B", "C", "D", "E", "F"]:
        for num in range(1, 11):
            if row in ["A", "B"]:
                price = 300
            elif row in ["C", "D"]:
                price = 200
            else:
                price = 150

            Seat.objects.create(
                seat_number=f"{row}{num}",
                show=show,
                is_booked=False,
                price=price,
            )


def generate_ticket_pdf_buffer(booking):
    site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000")
    verification_url = f"{site_url}/ticket/verify/{booking.id}/"

    qr_data = (
        f"ShowTime Ticket Verification\n"
        f"Verify URL: {verification_url}\n"
        f"Booking ID: {booking.id}\n"
        f"Movie: {booking.movie_name}\n"
        f"Show Time: {booking.show_time}\n"
        f"Seats: {booking.seats}\n"
        f"Amount: ₹{booking.amount}\n"
        f"Payment Method: {booking.payment_method}\n"
        f"Status: {'Paid' if booking.payment_status else 'Pending'}"
    )

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFillColor(colors.HexColor("#0f0f0f"))
    p.rect(0, 0, width, height, fill=1, stroke=0)

    card_x = 40
    card_y = 80
    card_w = width - 80
    card_h = height - 140

    p.setFillColor(colors.HexColor("#1a1a1a"))
    p.setStrokeColor(colors.HexColor("#2f2f2f"))
    p.setLineWidth(1)
    p.roundRect(card_x, card_y, card_w, card_h, 18, fill=1, stroke=1)

    p.setFillColor(colors.HexColor("#ff4d4d"))
    p.roundRect(card_x, height - 120, card_w, 40, 18, fill=1, stroke=0)

    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(card_x + 20, height - 108, "SHOWTIME")

    p.setFont("Helvetica", 11)
    p.drawRightString(card_x + card_w - 20, height - 108, "Movie Ticket Booking")

    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 24)
    p.drawString(card_x + 20, height - 165, "Booking Confirmed")

    p.setFont("Helvetica", 12)
    p.setFillColor(colors.HexColor("#cfcfcf"))
    p.drawString(card_x + 20, height - 185, "Please present this ticket at the theatre entry.")

    badge_x = card_x + card_w - 170
    badge_y = height - 182
    badge_w = 150
    badge_h = 26

    if booking.payment_status:
        badge_color = colors.HexColor("#00c853")
        badge_text = "PAID"
    else:
        badge_color = colors.HexColor("#ffab00")
        badge_text = "PENDING"

    p.setFillColor(badge_color)
    p.roundRect(badge_x, badge_y, badge_w, badge_h, 8, fill=1, stroke=0)
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(badge_x + badge_w / 2, badge_y + 8, f"STATUS: {badge_text}")

    p.setStrokeColor(colors.HexColor("#3a3a3a"))
    p.line(card_x + 20, height - 205, card_x + card_w - 20, height - 205)

    info_x = card_x + 25
    info_y = height - 245
    line_gap = 28

    details = [
        ("Booking ID", f"#{booking.id}"),
        ("Movie", booking.movie_name),
        ("Show Time", booking.show_time),
        ("Seats", booking.seats),
        ("Amount Paid", f"₹{booking.amount}"),
        ("Payment Method", booking.payment_method),
        ("Booking Date", booking.booked_at.strftime("%d %b %Y, %I:%M %p")),
    ]

    for label, value in details:
        p.setFillColor(colors.HexColor("#bdbdbd"))
        p.setFont("Helvetica-Bold", 11)
        p.drawString(info_x, info_y, label)
        p.setFillColor(colors.white)
        p.setFont("Helvetica", 12)
        p.drawString(info_x + 120, info_y, str(value))
        info_y -= line_gap

    qr_panel_x = card_x + card_w - 210
    qr_panel_y = card_y + 120
    qr_panel_w = 170
    qr_panel_h = 210

    p.setFillColor(colors.HexColor("#111111"))
    p.setStrokeColor(colors.HexColor("#444444"))
    p.roundRect(qr_panel_x, qr_panel_y, qr_panel_w, qr_panel_h, 12, fill=1, stroke=1)

    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(qr_panel_x + qr_panel_w / 2, qr_panel_y + qr_panel_h - 20, "SCAN QR CODE")

    qr_reader = ImageReader(qr_buffer)
    p.drawImage(
        qr_reader,
        qr_panel_x + 25,
        qr_panel_y + 45,
        width=120,
        height=120,
        mask="auto",
    )

    p.setFillColor(colors.HexColor("#cfcfcf"))
    p.setFont("Helvetica", 9)
    p.drawCentredString(qr_panel_x + qr_panel_w / 2, qr_panel_y + 28, "For entry verification")

    p.setStrokeColor(colors.HexColor("#3a3a3a"))
    p.line(card_x + 20, card_y + 90, card_x + card_w - 20, card_y + 90)

    p.setFillColor(colors.HexColor("#bdbdbd"))
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(card_x + 20, card_y + 60, "Keep this ticket safe. QR code is required at the entry gate.")
    p.drawString(card_x + 20, card_y + 45, "Powered by ShowTime • Enjoy your movie experience 🎬")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


def send_otp_email(receiver_email, otp):
    print("Sending OTP to:", receiver_email)
    send_mail(
        "ShowTime OTP Verification",
        f"Your OTP is {otp}",
        getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
        [receiver_email],
        fail_silently=False,
    )
    print("send_mail completed")


def send_booking_confirmation_email(user_email, booking):
    if not user_email:
        return

    subject = f"ShowTime Booking Confirmed - {booking.movie_name}"
    html_content = f"""
    <h2>Booking Confirmed 🎟</h2>
    <p><b>Movie:</b> {booking.movie_name}</p>
    <p><b>Show Time:</b> {booking.show_time}</p>
    <p><b>Seats:</b> {booking.seats}</p>
    <p><b>Amount:</b> ₹{booking.amount}</p>
    <p><b>Payment:</b> {booking.payment_method}</p>
    <p>Thank you for booking with <b>ShowTime</b> 🍿</p>
    """

    email = EmailMessage(
        subject,
        html_content,
        getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
        [user_email],
    )
    email.content_subtype = "html"

    try:
        pdf_buffer = generate_ticket_pdf_buffer(booking)
        email.attach(
            f"ShowTime_Ticket_{booking.id}.pdf",
            pdf_buffer.getvalue(),
            "application/pdf",
        )
    except Exception as e:
        print("PDF ATTACHMENT ERROR:", e)

    try:
        email.send()
    except Exception as e:
        print("BOOKING EMAIL ERROR:", e)


def release_expired_locks():
    Seat.objects.filter(
        is_locked=True,
        lock_expires_at__isnull=False,
        lock_expires_at__lt=timezone.now(),
    ).update(
        is_locked=False,
        locked_by="",
        locked_at=None,
        lock_expires_at=None,
    )


def lock_seats(seats, lock_owner, minutes=5):
    expires_at = timezone.now() + timedelta(minutes=minutes)
    for seat in seats:
        seat.is_locked = True
        seat.locked_by = lock_owner
        seat.locked_at = timezone.now()
        seat.lock_expires_at = expires_at
        seat.save()
    return expires_at


def get_youtube_trailer_url(movie_title: str):
    api_key = getattr(settings, "YOUTUBE_API_KEY", None)
    if not api_key:
        return None

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{movie_title} official trailer",
        "type": "video",
        "order": "viewCount",
        "videoEmbeddable": "true",
        "maxResults": 5,
        "key": api_key,
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            return None
        video_id = items[0]["id"]["videoId"]
        return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        return None


def release_seats_for_booking(booking):
    show = Show.objects.filter(
        movie_name__iexact=booking.movie_name,
        show_time=str(booking.show_time),
    ).first()
    if not show:
        return

    seat_numbers = [s.strip() for s in (booking.seats or "").split(",") if s.strip()]
    Seat.objects.filter(
        show=show,
        seat_number__in=seat_numbers,
    ).update(
        is_booked=False,
        is_locked=False,
        locked_by="",
        locked_at=None,
        lock_expires_at=None,
    )


def get_user_preferred_genres(user):
    if not BOOKING_HAS_USER_FIELD:
        return []

    try:
        bookings = Booking.objects.filter(user=user).order_by("-booked_at")
    except Exception:
        return []

    genre_counter = {}
    for booking in bookings:
        movie = Movie.objects.filter(title__iexact=booking.movie_name).first()
        if not movie:
            continue
        genres = [g.strip() for g in (movie.genre or "").split(",") if g.strip()]
        for genre in genres:
            genre_counter[genre] = genre_counter.get(genre, 0) + 1

    sorted_genres = sorted(genre_counter.items(), key=lambda x: x[1], reverse=True)
    return [genre for genre, _ in sorted_genres[:3]]


def get_trending_movies():
    recent_days = timezone.now() - timedelta(days=7)
    trending_scores = {}
    movies = Movie.objects.filter(is_active=True)

    tmdb_image_base_url = getattr(
        settings,
        "TMDB_IMAGE_BASE_URL",
        "https://image.tmdb.org/t/p/w500"
    )

    for movie in movies:
        score = 0.0
        rating = float(movie.rating or 0)
        votes = int(movie.vote_count or 0)

        # Base score from rating and popularity
        score += rating * 10
        score += min(votes / 100, 25)

        # Recent bookings boost
        recent_bookings = Booking.objects.filter(
            movie_name=movie.title,
            booked_at__gte=recent_days,
        ).count()
        score += recent_bookings * 15

        # Release date boost / recency boost
        try:
            if movie.release_date:
                if isinstance(movie.release_date, str):
                    release_date = datetime.fromisoformat(movie.release_date).date()
                else:
                    release_date = movie.release_date

                days_old = (timezone.localdate() - release_date).days
                if days_old <= 30:
                    score += 20
                elif days_old <= 90:
                    score += 10
        except Exception:
            pass

        # Poster URL fix
        poster_path = movie.poster_path or ""
        if poster_path and not poster_path.startswith("http"):
            poster_path = f"{tmdb_image_base_url}{poster_path}"

        trending_scores[movie.id] = {
            "id": movie.id,
            "title": movie.title,
            "overview": movie.overview or "",
            "poster_path": poster_path,
            "genre": movie.genre or "",
            "rating": movie.rating or 0,
            "vote_count": movie.vote_count or 0,
            "release_date": movie.release_date,
            "budget_level": movie.budget_level or "medium",
            "score": score,
        }

    sorted_movies = sorted(
        trending_scores.values(),
        key=lambda x: x["score"],
        reverse=True
    )

    return sorted_movies[:10]

def get_continue_watching(user):
    if not user.is_authenticated:
        return []

    watching = (
        ContinueWatching.objects
        .filter(user=user, completed=False)
        .select_related("movie")
        .order_by("-updated_at")
    )
    return watching[:10]


def get_because_you_watched(user):
    if not user.is_authenticated:
        return []

    watched = (
        ContinueWatching.objects
        .filter(user=user)
        .select_related("movie")
        .order_by("-updated_at")[:3]
    )

    recommendation_sections = []

    for item in watched:
        movie = item.movie
        genres = movie.genre.lower().split(",") if movie.genre else []

        similar_movies = Movie.objects.filter(is_active=True).exclude(id=movie.id)

        for genre in genres[:2]:
            similar_movies = similar_movies.filter(genre__icontains=genre.strip())

        similar_movies = similar_movies.order_by("-rating")[:10]
        recommendation_sections.append(
            {
                "title": f"Because You Watched {movie.title}",
                "movies": similar_movies,
            }
        )

    return recommendation_sections


def get_wishlist_movie_ids(request):
    if not request.user.is_authenticated:
        return []
    return list(Wishlist.objects.filter(user=request.user).values_list("movie_id", flat=True))


# ---------------------------
# SIGNUP / OTP / AUTH
# ---------------------------

def signup_view(request): #This handles new user signup. It checks username, email, and password, then validates them. If everything is fine, it creates the user, sends an OTP to email, saves the OTP in session, and sends the user to the OTP verification page
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not username or not email or not password:
            return render(request, "booking/signup.html", {"error": "All fields are required"})

        if len(password) < 6:
            return render(request, "booking/signup.html", {"error": "Password must be at least 6 characters"})

        if not any(char.isdigit() for char in password):
            return render(request, "booking/signup.html", {"error": "Password must contain a number"})

        if User.objects.filter(username=username).exists():
            return render(request, "booking/signup.html", {"error": "Username already exists"})

        if User.objects.filter(email=email).exists():
            return render(request, "booking/signup.html", {"error": "Email already registered"})

        user = User.objects.create_user(username=username, email=email, password=password)
        otp = random.randint(100000, 999999)

        try:
            send_otp_email(email, otp)
        except Exception as e:
            user.delete()
            print("MAIL ERROR:", repr(e))
            return render(
                request,
                "booking/signup.html",
                {"error": "OTP could not be sent. Check SendGrid setup."},
            )

        request.session["signup_otp"] = str(otp)
        request.session["signup_user_id"] = user.id
        return redirect("/verify-signup-otp/")

    return render(request, "booking/signup.html")


def signup_otp(request): #This checks the OTP entered during signup. If it matches the saved OTP, the user is logged in and redirected to /movies/
    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        saved_otp = request.session.get("signup_otp")

        if entered_otp == saved_otp:
            user_id = request.session.get("signup_user_id")
            user = get_object_or_404(User, id=user_id)
            login(request, user)
            request.session.pop("signup_otp", None)
            request.session.pop("signup_user_id", None)
            return redirect("/movies/")

        return render(request, "booking/verify_signup_otp.html", {"error": "Invalid OTP"})

    return render(request, "booking/verify_signup_otp.html")


def otp_login(request): #This is for login with email + OTP. It checks whether the email exists, sends an OTP to that email, stores OTP and user id in session, and redirects to the OTP verification page.
    if request.method == "POST":
        email = request.POST.get("email")
        user = User.objects.filter(email=email).first()

        if not user:
            return render(
                request,
                "booking/otp_login.html",
                {"error": "Email not registered"},
            )

        otp = random.randint(100000, 999999)
        print("OTP login started for:", email)

        try:
            send_otp_email(user.email, otp)
            print("OTP mail function finished")
        except Exception as e:
            print("MAIL ERROR:", repr(e))
            return render(
                request,
                "booking/otp_login.html",
                {"error": "OTP could not be sent. Check SendGrid setup."},
            )

        request.session["otp"] = str(otp)
        request.session["user_id"] = user.id
        return redirect("/verify-otp/")

    return render(request, "booking/otp_login.html")


def verify_otp(request):
    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        saved_otp = request.session.get("otp")

        if entered_otp == saved_otp:
            user_id = request.session.get("user_id")
            user = get_object_or_404(User, id=user_id)
            login(request, user)
            request.session.pop("otp", None)
            request.session.pop("user_id", None)
            return redirect("/movies/")

        return render(request, "booking/verify_otp.html", {"error": "Invalid OTP"})

    return render(request, "booking/verify_otp.html")


def logout_view(request):
    logout(request)
    return redirect("/")


# ---------------------------
# HOME / MOVIES / DETAILS
# ---------------------------

def home(request): #Shows the home page. It loads trending movies, wishlist items, continue-watching items, and “because you watched” suggestions.
    trending_movies = get_trending_movies()
    wishlist_movie_ids = get_wishlist_movie_ids(request)

    continue_watching = []
    because_sections = []

    if request.user.is_authenticated:
        continue_watching = get_continue_watching(request.user)
        because_sections = get_because_you_watched(request.user)

    return render(
        request,
        "booking/home.html",
        {
            "movies": trending_movies,
            "continue_watching": continue_watching,
            "because_sections": because_sections,
            "wishlist_movie_ids": wishlist_movie_ids,
        },
    )


def movies(request): #Shows the movies listing page. It can search movies by title/genre and filter by genre. It also builds the genre list for filters     
    query = request.GET.get("q", "").strip()
    selected_genre = request.GET.get("genre", "").strip()

    movies_qs = Movie.objects.filter(is_active=True)

    if query:
        movies_qs = movies_qs.filter(Q(title__icontains=query) | Q(genre__icontains=query))

    if selected_genre:
        movies_qs = movies_qs.filter(genre__icontains=selected_genre)

    all_genres = []
    genre_movies = Movie.objects.exclude(genre="")
    for movie in genre_movies:
        for g in movie.genre.split(","):
            g = g.strip()
            if g and g not in all_genres:
                all_genres.append(g)
    all_genres.sort()

    return render(
        request,
        "booking/movies.html",
        {
            "movies": movies_qs,
            "query": query,
            "selected_genre": selected_genre,
            "all_genres": all_genres,
            "wishlist_movie_ids": get_wishlist_movie_ids(request),
        },
    )


@login_required 
def movie_detail(request, movie_id): #Shows the full details of one movie. It gets the movie by ID, finds a trailer from TMDb or YouTube, and sends all data to the detail page.
    movie = get_object_or_404(Movie, id=movie_id, is_active=True)

    trailer_key = None
    trailer_url = get_youtube_trailer_url(movie.title)
    tmdb_api_key = getattr(settings, "TMDB_API_KEY", None)

    if tmdb_api_key and movie.tmdb_id:
        videos_url = f"https://api.themoviedb.org/3/movie/{movie.tmdb_id}/videos"
        params = {"api_key": tmdb_api_key, "language": "en-US"}
        try:
            response = requests.get(videos_url, params=params, timeout=15)
            response.raise_for_status()
            videos = response.json().get("results", [])

            official_trailer = None
            trailer_or_teaser = None
            any_youtube = None

            for video in videos:
                if video.get("site") != "YouTube" or not video.get("key"):
                    continue
                if any_youtube is None:
                    any_youtube = video
                if video.get("type") in ["Trailer", "Teaser"] and trailer_or_teaser is None:
                    trailer_or_teaser = video
                if video.get("type") == "Trailer" and video.get("official") is True:
                    official_trailer = video
                    break

            chosen = official_trailer or trailer_or_teaser or any_youtube
            if chosen:
                trailer_key = chosen.get("key")
                trailer_url = f"https://www.youtube.com/watch?v={trailer_key}"
        except requests.RequestException:
            pass

    return render(
        request,
        "booking/movie_detail.html",
        {
            "movie": movie,
            "trailer_key": trailer_key,
            "trailer_url": trailer_url,
        },
    )


# ---------------------------
# SHOW TIMINGS / SEATS
# ---------------------------

@login_required
def show_timings(request): #This shows all available show times for a selected movie. If no shows exist, it creates default timings like 10 AM, 2 PM, and 6 PM, then makes seats for them.
    movie_id = request.GET.get("movie_id")
    if not movie_id:
        return redirect("/movies/")

    movie = get_object_or_404(Movie, id=movie_id, is_active=True)
    shows = Show.objects.filter(movie_name__iexact=movie.title).order_by("show_time")

    if not shows.exists():
        default_times = ["10:00:00", "14:00:00", "18:00:00"]
        for time_str in default_times:
            show = Show.objects.create(movie_name=movie.title, show_time=time_str)
            ensure_seats_for_show(show)
        shows = Show.objects.filter(movie_name__iexact=movie.title).order_by("show_time")
    else:
        for show in shows:
            ensure_seats_for_show(show)

    return render(
        request,
        "booking/show_timings.html",
        {"movie": movie.title, "shows": shows},
    )


@login_required
def show_seats(request): #This shows all seats for one selected show. It also stores show details in session so the booking flow can continue.
    show_id = request.GET.get("show_id")
    if not show_id:
        return redirect("/movies/")

    release_expired_locks()
    show = get_object_or_404(Show, id=show_id)
    ensure_seats_for_show(show)

    seats = Seat.objects.filter(show=show).order_by("seat_number")
    request.session["show_id"] = show.id
    request.session["movie_name"] = show.movie_name
    request.session["show_time"] = str(show.show_time)

    return render(
    request,
    "booking/seats.html",
    {
        "show": show,
        "seats": seats,
        "movie": show.movie_name,
        "show_time": show.show_time,
        "now": timezone.now(),
    },
)


@login_required
def book_seat(request, seat_id): #This books one seat safely using transaction.atomic(). It first checks whether the seat is already booked or locked.
    with transaction.atomic():
        seat = Seat.objects.select_for_update().get(id=seat_id)
        if seat.is_booked:
            return HttpResponse("Seat already booked")
        if seat.is_locked and seat.lock_expires_at and seat.lock_expires_at > timezone.now():
            return HttpResponse("Seat temporarily locked")
        seat.is_booked = True
        seat.save()

    return HttpResponse("Seat booked successfully")


@login_required
def book_multiple(request): #Why used: this is the main seat-booking + payment step.
    if request.method != "POST":
        return HttpResponse("Invalid request", status=405)

    selected_seats = request.POST.getlist("selected_seats")
    show_id = request.POST.get("show_id")

    print("POST DATA:", request.POST)
    print("selected_seats:", selected_seats)
    print("show_id:", show_id)

    if not selected_seats:
        return HttpResponse("No seats selected", status=400)

    if not show_id:
        return HttpResponse("Show ID missing", status=400)

    show = get_object_or_404(Show, id=show_id)

    seats_qs = Seat.objects.filter(show=show, seat_number__in=selected_seats)

    if seats_qs.count() != len(selected_seats):
        return HttpResponse("One or more seats are invalid", status=400)

    if seats_qs.filter(is_booked=True).exists():
        return HttpResponse("One or more selected seats are already booked", status=400)

    if seats_qs.filter(is_locked=True).exists():
        return HttpResponse("One or more selected seats are locked", status=400)

    total_price = sum(int(seat.price) for seat in seats_qs)

    # Save session first
    request.session["selected_seats"] = selected_seats
    request.session["show_id"] = show.id
    request.session["total_price"] = str(total_price)
    request.session.modified = True
    request.session.save()

    # Razorpay client
    try:
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    except Exception as e:
        return HttpResponse(f"Razorpay client creation failed: {e}", status=500)

    # Create order
    order_data = {
        "amount": int(total_price * 100),
        "currency": "INR",
        "payment_capture": "1",
    }

    try:
        order = client.order.create(data=order_data)
    except Exception as e:
        return HttpResponse(f"Razorpay order creation failed: {e}", status=500)

    print("ORDER CREATED:", order)

    request.session["razorpay_order_id"] = order["id"]
    request.session.save()

    return render(request, "booking/payment.html", {
        "show": show,
        "selected_seats": selected_seats,
        "total_price": total_price,
        "order_id": order["id"],
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": int(total_price * 100),
        "currency": "INR",
    })
# ---------------------------
# PAYMENT
# ---------------------------

@login_required
def payment_view(request): #Why used: to collect the total amount before payment.
    release_expired_locks()

    seat_ids = request.session.get("booked_seats", [])
    if not seat_ids:
        return HttpResponseBadRequest("No seats found in session")

    movie_name = request.session.get("movie_name", "Unknown Movie")
    show_time = request.session.get("show_time", "Unknown Time")
    seats = request.session.get("seats", "N/A")
    ticket_total = Decimal(str(request.session.get("amount", 0) or 0))
    lock_expires_at = request.session.get("lock_expires_at")

    if ticket_total <= 0:
        return redirect("/seats/")

    if not lock_expires_at:
        return redirect("/seats/")

    try:
        expires_at = datetime.fromisoformat(lock_expires_at)
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at)
    except Exception:
        return redirect("/seats/")

    if timezone.now() > expires_at:
        request.session.pop("booked_seats", None)
        request.session.pop("show_id", None)
        request.session.pop("movie_name", None)
        request.session.pop("show_time", None)
        request.session.pop("seats", None)
        request.session.pop("amount", None)
        request.session.pop("lock_expires_at", None)
        return redirect("/seats/")

    food_cart = FoodCartItem.objects.filter(user=request.user).select_related("food_item")
    food_total = sum((Decimal(str(item.total_price)) for item in food_cart), Decimal("0.00"))

    offer_discount = Decimal("0.00")
    grand_total = ticket_total + food_total

    if grand_total >= Decimal("1000.00"):
        offer_discount = Decimal("150.00")

    final_total = grand_total - offer_discount

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order = client.order.create({
        "amount": int(final_total * 100),
        "currency": "INR",
        "payment_capture": 1,
    })

    request.session["razorpay_order_id"] = order["id"]

    return render(
        request,
        "booking/payment.html",
        {
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "order_id": order["id"],
            "amount": int(ticket_total),
            "razorpay_amount": int(final_total * 100),
            "movie_name": movie_name,
            "show_time": show_time,
            "seats": seats,
            "lock_expires_at": lock_expires_at,
            "food_cart": food_cart,
            "food_total": food_total,
            "offer_discount": offer_discount,
            "grand_total": final_total,
        },
    )

# ---------------------------
# PAYMENT success
# ---------------------------

@csrf_exempt
def payment_success(request): #to save the booking only after payment is successful.
    print("SESSION:", dict(request.session))

    seats = request.session.get("selected_seats")
    show_id = request.session.get("show_id")
    total_price = request.session.get("total_price")

    razorpay_order_id = request.POST.get("razorpay_order_id", "")
    razorpay_payment_id = request.POST.get("razorpay_payment_id", "")
    razorpay_signature = request.POST.get("razorpay_signature", "")


    if not seats:
        return HttpResponse("No seats found in session", status=400)

    if not show_id:
        return HttpResponse("Show not found in session", status=400)

    try:
        show = Show.objects.get(id=show_id)
    except Show.DoesNotExist:
        return HttpResponse("Invalid show", status=404)

    try:
        with transaction.atomic():
            booking = Booking.objects.create(
                user=request.user if request.user.is_authenticated else None,
                movie_name=show.movie_name,
                show_time=show.show_time,
                seats=", ".join(seats),
                amount=int(total_price),
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                payment_status=True,
                payment_method="Razorpay",
            )

            Seat.objects.filter(
                show=show,
                seat_number__in=seats
            ).update(
                is_booked=True,
                is_locked=False
            )

            for key in [
                "selected_seats",
                "show_id",
                "total_price",
                "razorpay_order_id"
            ]:
                request.session.pop(key, None)

        return render(request, "booking/payment_success.html", {
            "booking": booking
        })

    except Exception as e:
        return HttpResponse(f"Booking failed: {e}", status=500)
# ---------------------------
# INITIATE PAYMENT
# ---------------------------

@login_required
def initiate_payment(request, show_id): #to begin the payment process after seat selection.
    show = get_object_or_404(Show, id=show_id)

    if request.method == "POST":
        print("POST DATA:", request.POST)

        selected_seats = request.POST.getlist("selected_seats")
        print("SELECTED SEATS FROM FORM:", selected_seats)

        if not selected_seats:
            return HttpResponse("No seats selected", status=400)

        seat_price = Decimal(str(show.price))
        total_price = seat_price * len(selected_seats)

        request.session["selected_seats"] = selected_seats
        request.session["show_id"] = show.id
        request.session["total_price"] = str(total_price)
        request.session.modified = True
        request.session.save()

        print("SESSION SAVED IN INITIATE:", dict(request.session))

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        order_data = {
            "amount": int(total_price * 100),
            "currency": "INR",
            "payment_capture": "1",
        }

        order = client.order.create(data=order_data)
        request.session["razorpay_order_id"] = order["id"]
        request.session.save()

        return render(request, "booking/payment.html", {
            "show": show,
            "selected_seats": selected_seats,
            "total_price": total_price,
            "order_id": order["id"],
            "razorpay_key": settings.RAZORPAY_KEY_ID,
            "amount": int(total_price * 100),
            "currency": "INR",
        })


    return HttpResponse("Invalid request", status=405)
# ---------------------------
# HISTORY / PDF
# ---------------------------

@login_required
def my_bookings(request): #to let users see their past tickets
    if BOOKING_HAS_USER_FIELD:
        bookings = Booking.objects.filter(user=request.user).order_by("-booked_at")
    else:
        bookings = Booking.objects.all().order_by("-booked_at")

    return render(request, "booking/history.html", {"bookings": bookings})


@login_required
def download_ticket_pdf(request, booking_id): #to give users a printable ticket.
    booking = get_object_or_404(Booking, id=booking_id)

    if BOOKING_HAS_USER_FIELD and not request.user.is_staff and booking.user_id != request.user.id:
        return HttpResponseBadRequest("You are not allowed to download this ticket.")

    buffer = generate_ticket_pdf_buffer(booking)
    return FileResponse(buffer, as_attachment=True, filename=f"ticket_{booking.id}.pdf")


# ---------------------------
# ADMIN DASHBOARD / MOVIES / SHOWS / BOOKINGS
# ---------------------------

@staff_member_required
def admin_dashboard(request): #to give the admin a quick overview.
    total_movies = Movie.objects.filter(is_active=True).count()
    total_shows = Show.objects.count()
    total_bookings = Booking.objects.filter(payment_status=True).count()
    total_earnings = Booking.objects.filter(payment_status=True).aggregate(total=Sum("amount"))["total"] or 0
    recent_bookings = Booking.objects.all().order_by("-booked_at")[:8]

    return render(
        request,
        "booking/admin_dashboard.html",
        {
            "total_movies": total_movies,
            "total_shows": total_shows,
            "total_bookings": total_bookings,
            "total_earnings": total_earnings,
            "recent_bookings": recent_bookings,
        },
    )


@staff_member_required
def admin_movies(request): #to manage movies 
    movies = Movie.objects.all().order_by("-id")
    return render(request, "booking/admin_movies.html", {"movies": movies})


@staff_member_required
def admin_add_movie(request): #to add movies into ShowTime.
    if request.method == "POST":
        title = request.POST.get("title")
        overview = request.POST.get("overview")
        poster_path = request.POST.get("poster_path")
        backdrop_path = request.POST.get("backdrop_path")
        release_date = request.POST.get("release_date")
        duration = request.POST.get("duration") or 0
        rating = request.POST.get("rating") or 0
        vote_count = request.POST.get("vote_count") or 0
        genre = request.POST.get("genre") or ""
        tmdb_id = request.POST.get("tmdb_id") or None
        is_active = request.POST.get("is_active") == "on"

        Movie.objects.create(
            title=title,
            overview=overview,
            poster_path=poster_path,
            backdrop_path=backdrop_path,
            release_date=release_date if release_date else None,
            duration=int(duration) if duration else 0,
            rating=float(rating) if rating else 0,
            vote_count=int(vote_count) if vote_count else 0,
            genre=genre,
            tmdb_id=int(tmdb_id) if tmdb_id else None,
            is_active=is_active,
        )
        return redirect("/admin-movies/")

    return render(request, "booking/admin_add_movie.html")


@staff_member_required
def admin_delete_movie(request, movie_id): #to remove movies no longer needed
    movie = get_object_or_404(Movie, id=movie_id)
    movie.delete()
    return redirect("/admin-movies/")


@staff_member_required
def admin_shows(request): #to manage show timings.
    shows = Show.objects.all().order_by("-id")
    movies = Movie.objects.filter(is_active=True).order_by("title")
    return render(request, "booking/admin_shows.html", {"shows": shows, "movies": movies})


@staff_member_required
def admin_add_show(request): #to add new show slots.
    movies = Movie.objects.filter(is_active=True).order_by("title")

    if request.method == "POST":
        movie_id = request.POST.get("movie_id")
        show_time = request.POST.get("show_time")
        movie = get_object_or_404(Movie, id=movie_id, is_active=True)
        show = Show.objects.create(movie_name=movie.title, show_time=show_time)
        ensure_seats_for_show(show)
        return redirect("/admin-shows/")

    return render(request, "booking/admin_add_show.html", {"movies": movies})


@staff_member_required
def admin_delete_show(request, show_id): #to remove unwanted show timings.
    show = get_object_or_404(Show, id=show_id)
    show.delete()
    return redirect("/admin-shows/")


@staff_member_required
def admin_bookings(request): #to give the admin booking analytics and reports.
    bookings = Booking.objects.all().order_by("-booked_at")

    total_earnings = Booking.objects.filter(payment_status=True).aggregate(total=Sum("amount"))["total"] or 0
    total_bookings = Booking.objects.filter(payment_status=True).count()

    top_movies_qs = (
        Booking.objects.filter(payment_status=True)
        .values("movie_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )
    top_movies_labels = [item["movie_name"] for item in top_movies_qs]
    top_movies_counts = [item["count"] for item in top_movies_qs]

    today = timezone.localdate()
    start_date = today - timedelta(days=6)

    earnings_qs = (
        Booking.objects.filter(payment_status=True, booked_at__date__gte=start_date)
        .annotate(day=TruncDate("booked_at"))
        .values("day")
        .annotate(total=Sum("amount"))
        .order_by("day")
    )
    earnings_map = {item["day"]: item["total"] for item in earnings_qs}

    daily_labels = []
    daily_earnings = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        daily_labels.append(day.strftime("%d %b"))
        daily_earnings.append(int(earnings_map.get(day, 0) or 0))

    total_seats = Seat.objects.count()
    booked_seats = Seat.objects.filter(is_booked=True).count()
    occupancy_percent = round((booked_seats / total_seats) * 100, 1) if total_seats else 0

    peak_show_qs = (
        Booking.objects.filter(payment_status=True)
        .values("show_time")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )
    peak_show_labels = [item["show_time"] for item in peak_show_qs]
    peak_show_counts = [item["count"] for item in peak_show_qs]

    return render(
        request,
        "booking/admin_bookings.html",
        {
            "bookings": bookings,
            "total_earnings": total_earnings,
            "total_bookings": total_bookings,
            "top_movies_labels": top_movies_labels,
            "top_movies_counts": top_movies_counts,
            "daily_labels": daily_labels,
            "daily_earnings": daily_earnings,
            "occupancy_percent": occupancy_percent,
            "booked_seats": booked_seats,
            "total_seats": total_seats,
            "peak_show_labels": peak_show_labels,
            "peak_show_counts": peak_show_counts,
        },
    )


# ---------------------------
# AI RECOMMENDATION
# ---------------------------

@login_required
def ai_recommend(request): #to give smart, personalized movie recommendations in ShowTime.
    query = request.GET.get("q", "").strip().lower()
    budget = request.GET.get("budget", "").strip().lower()
    genre_filter = request.GET.get("genre", "").strip().lower()
    min_rating = request.GET.get("min_rating", "").strip()
    sort_by = request.GET.get("sort_by", "").strip()

    movies = Movie.objects.filter(is_active=True)
    preferred_genres = get_user_preferred_genres(request.user)
    trending_movies = get_trending_movies()
    trending_ids = [tm.id for tm in trending_movies]

    if budget in ["low", "medium", "high"] and MOVIE_HAS_BUDGET_FIELD:
        try:
            movies = movies.filter(budget_level=budget)
        except Exception:
            pass

    if genre_filter:
        movies = movies.filter(genre__icontains=genre_filter)

    if min_rating:
        try:
            movies = movies.filter(rating__gte=float(min_rating))
        except ValueError:
            pass

    def safe_float(value):
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    def safe_int(value):
        try:
            return int(value or 0)
        except Exception:
            return 0

    mood_map = {
        "sad": ["drama", "romance"],
        "emotional": ["drama", "romance"],
        "happy": ["comedy", "animation", "family"],
        "funny": ["comedy"],
        "romantic": ["romance"],
        "scary": ["horror", "thriller"],
        "horror": ["horror"],
        "thrilling": ["thriller", "action", "mystery"],
        "action": ["action", "adventure"],
        "adventure": ["adventure", "fantasy"],
        "space": ["sci-fi"],
        "sci-fi": ["sci-fi"],
        "family": ["family", "animation", "adventure"],
        "dark": ["thriller", "crime", "horror"],
        "mystery": ["mystery", "thriller"],
    }
    popular_words = {"popular", "trending", "best", "top", "hit", "famous"}

    scored_movies = []
    for movie in movies:
        title = (movie.title or "").lower()
        genre = (movie.genre or "").lower()
        overview = (movie.overview or "").lower()
        rating = safe_float(movie.rating)
        votes = safe_int(movie.vote_count)
        budget_level = (getattr(movie, "budget_level", "") or "").lower()

        score = 0.0
        reasons = []

        if movie.id in trending_ids:
            trend_position = trending_ids.index(movie.id) + 1
            score += max(40 - trend_position * 3, 10)
            reasons.append("Trending Now")

        movie_genres = [g.strip().lower() for g in (movie.genre or "").split(",") if g.strip()]
        for pref in preferred_genres:
            if pref.lower() in movie_genres or pref.lower() in genre:
                score += 50
                reasons.append(f"Because you watched {pref}")

        if query:
            terms = [t for t in re.split(r"[\s,]+", query) if t]

            if query in title:
                score += 60
                reasons.append("Title match")
            if query in genre:
                score += 45
                reasons.append("Genre match")
            if query in overview:
                score += 20
                reasons.append("Description match")

            for term in terms:
                if term in popular_words:
                    score += 15
                    reasons.append("Popular choice")

                mapped_genres = mood_map.get(term, [])
                for mapped in mapped_genres:
                    if mapped in genre:
                        score += 35
                        reasons.append(f"{term.title()} vibe")
                        break

                if term in title:
                    score += 25
                if term in overview:
                    score += 10
        else:
            score += rating * 12
            score += min(votes / 50, 30)
            reasons.append("Trending pick")

        if budget in ["low", "medium", "high"] and MOVIE_HAS_BUDGET_FIELD:
            if budget_level == budget:
                score += 25
                reasons.append(f"{budget.title()} budget")
            else:
                score -= 10

        score += rating * 10
        score += min(votes / 100, 25)

        if rating >= 8:
            score += 8
            reasons.append("High rated")
        if votes >= 1000:
            score += 5
            reasons.append("Popular")

        release_date = getattr(movie, "release_date", None)
        try:
            if release_date:
                if isinstance(release_date, str):
                    release_date = datetime.fromisoformat(release_date).date()
                days_old = (timezone.localdate() - release_date).days
                if days_old <= 180:
                    score += 8
                    reasons.append("New release")
        except Exception:
            pass

        scored_movies.append(
            {
                "movie": movie,
                "score": round(score, 1),
                "reasons": list(dict.fromkeys(reasons))[:3],
            }
        )

    if sort_by == "rating":
        scored_movies.sort(key=lambda x: safe_float(x["movie"].rating), reverse=True)
    elif sort_by == "votes":
        scored_movies.sort(key=lambda x: safe_int(x["movie"].vote_count), reverse=True)
    elif sort_by == "title":
        scored_movies.sort(key=lambda x: (x["movie"].title or "").lower())
    else:
        scored_movies.sort(
            key=lambda item: (
                item["score"],
                safe_float(item["movie"].rating),
                safe_int(item["movie"].vote_count),
            ),
            reverse=True,
        )

    recommended = scored_movies[:12]

    return render(
        request,
        "booking/ai_recommend.html",
        {
            "query": query,
            "budget": budget,
            "genre_filter": genre_filter,
            "min_rating": min_rating,
            "sort_by": sort_by,
            "preferred_genres": preferred_genres,
            "trending_movies": trending_movies,
            "recommended": recommended,
        },
    )


# ---------------------------
# CANCEL BOOKING
# ---------------------------

@login_required
def cancel_booking(request, booking_id):
    if request.method != "POST":
        return redirect("/my-bookings/")

    if BOOKING_HAS_USER_FIELD and not request.user.is_staff:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    else:
        booking = get_object_or_404(Booking, id=booking_id)

    with transaction.atomic():
        release_seats_for_booking(booking)
        booking.delete()

    messages.success(request, "Booking cancelled successfully.")
    return redirect("/my-bookings/")


# ---------------------------
# WISHLIST
# ---------------------------

@login_required
def wishlist_page(request):
    wishlist_items = (
        Wishlist.objects.filter(user=request.user)
        .select_related("movie")
        .order_by("-id")
    )

    return render(
        request,
        "booking/wishlist.html",
        {"wishlist_items": wishlist_items},
    )


@login_required
def add_to_wishlist(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    Wishlist.objects.get_or_create(user=request.user, movie=movie)

    messages.success(request, f"{movie.title} added to wishlist ❤️")

    return redirect(request.META.get("HTTP_REFERER", "/movies/"))


@login_required 
def remove_from_wishlist(request, movie_id): 
    movie = get_object_or_404(Movie, id=movie_id)

    Wishlist.objects.filter(user=request.user, movie=movie).delete()

    messages.success(request, f"{movie.title} removed from wishlist")

    return redirect(request.META.get("HTTP_REFERER", "/wishlist/"))


# ---------------------------
# CHATBOT
# ---------------------------

@require_POST
def chatbot_reply(request): #to help users quickly get movie suggestions.
    data = json.loads(request.body or "{}")
    message = (data.get("message") or "").lower()

    reply = "🎬 Try exploring trending movies!"

    if "horror" in message:
        reply = "👻 Recommended Horror Movies: The Conjuring, Smile, Insidious, IT."
    elif "romantic" in message or "romance" in message:
        reply = "❤️ Romantic Picks: Titanic, The Notebook, La La Land."
    elif "action" in message:
        reply = "🔥 Action Movies: John Wick, Mad Max, Extraction."
    elif "comedy" in message:
        reply = "😂 Comedy Movies: Deadpool, Hangover, Free Guy."
    elif "sci" in message or "science fiction" in message:
        reply = "🚀 Sci-Fi Movies: Interstellar, Dune, Arrival."
    elif "thriller" in message:
        reply = "🕵 Thriller Movies: Prisoners, Se7en, Gone Girl."

    return JsonResponse({"reply": reply})


# ---------------------------
# FOOD OFFERS
# ---------------------------

@login_required
def food_offers(request): #to let users buy snacks with tickets.
    food_items = FoodItem.objects.filter(is_available=True)
    cart_items = FoodCartItem.objects.filter(user=request.user).select_related("food_item")
    cart_total = sum(item.total_price for item in cart_items)

    return render(
        request,
        "booking/food_offers.html",
        {
            "food_items": food_items,
            "cart_items": cart_items,
            "cart_total": cart_total,
        },
    )


@login_required
def add_food_to_cart(request, food_id): #to build the food order.
    if request.method != "POST":
        return redirect("food_offers")

    food = get_object_or_404(FoodItem, id=food_id, is_available=True)

    cart_item, created = FoodCartItem.objects.get_or_create(
        user=request.user,
        food_item=food,
        defaults={"quantity": 1},
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return redirect("food_offers")


@login_required
def remove_food_from_cart(request, food_id): #to delete food from order.
    if request.method != "POST":
        return redirect("food_offers")

    food = get_object_or_404(FoodItem, id=food_id)
    FoodCartItem.objects.filter(user=request.user, food_item=food).delete()

    return redirect("food_offers")


@login_required
def update_food_qty(request, food_id, action): #to manage cart items properly.
    if request.method != "POST":
        return redirect("food_offers")

    cart_item = get_object_or_404(
        FoodCartItem,
        user=request.user,
        food_item__id=food_id,
    )

    if action == "inc":
        cart_item.quantity += 1
        cart_item.save()
    elif action == "dec":
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()

    return redirect("food_offers")


# ---------------------------
# VERIFY TICKET
# ---------------------------

@staff_member_required
def verify_ticket(request, booking_id): #to stop ticket misuse at entry.
    booking = get_object_or_404(Booking, id=booking_id)

    if request.method == "POST":
        if booking.is_ticket_used:
            messages.warning(request, "This ticket has already been used.")
        else:
            booking.is_ticket_used = True
            booking.save()
            messages.success(request, "Ticket verified successfully.")

        return redirect("verify_ticket", booking_id=booking.id)

    return render(
        request,
        "booking/verify_ticket.html",
        {"booking": booking},
    )


# ---------------------------
# TICKETMASTER LIVE EVENTS
# ---------------------------


TICKETMASTER_BASE_URL = "https://app.ticketmaster.com/discovery/v2"


def _ticketmaster_get(path: str, params: dict | None = None): #to fetch live event data.
    api_key = getattr(settings, "TICKETMASTER_API_KEY", None)
    if not api_key:
        return None

    query_params = params.copy() if params else {}
    query_params["apikey"] = api_key

    url = f"{TICKETMASTER_BASE_URL}{path}?{urlencode(query_params)}"

    try:
        req = Request(url, headers={"User-Agent": "ShowTime/1.0"})
        with urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"Ticketmaster API error for {url}: {e}")
        return None


def _normalize_ticketmaster_event(item: dict, category: str): #to make API data easy to show in templates.
    images = item.get("images", [])
    poster_path = images[0].get("url", "") if images else ""

    start = item.get("dates", {}).get("start", {})
    local_date = start.get("localDate", "")
    local_time = start.get("localTime", "")

    venues = item.get("_embedded", {}).get("venues", [])
    venue = venues[0].get("name", "") if venues else ""

    description = (
        item.get("info")
        or item.get("pleaseNote")
        or item.get("description")
        or ""
    )

    price = 0
    price_ranges = item.get("priceRanges", [])
    if price_ranges:
        raw_price = price_ranges[0].get("min") or price_ranges[0].get("max") or 0
        try:
            price = int(float(raw_price))
        except (TypeError, ValueError):
            price = 0

    event_id = item.get("id", "")

    return {
        "slug": event_id,
        "id": event_id,
        "title": item.get("name", "Untitled Event"),
        "category": category,
        "description": description,
        "poster_path": poster_path,
        "date": local_date,
        "time": local_time,
        "venue": venue,
        "price": price,
        "ticket_url": item.get("url", ""),
        "highlights": [
            venue or "Venue TBA",
            local_date or "Date TBA",
            local_time or "Time TBA",
        ],
    }


def events(request): #to add events section in ShowTime.
    q = request.GET.get("q", "").strip()
    country = request.GET.get("country", "US").strip().upper()

    comedy_keyword = f"{q} comedy".strip() if q else "comedy"
    music_keyword = f"{q} music".strip() if q else "music"

    base_params = {
        "size": 12,
    }

    if country:
        base_params["countryCode"] = country

    comedy_payload = _ticketmaster_get("/events.json", {
        **base_params,
        "keyword": comedy_keyword,
    })

    music_payload = _ticketmaster_get("/events.json", {
        **base_params,
        "keyword": music_keyword,
    })

    comedy_raw = comedy_payload.get("_embedded", {}).get("events", []) if comedy_payload else []
    music_raw = music_payload.get("_embedded", {}).get("events", []) if music_payload else []

    comedy_events = [_normalize_ticketmaster_event(item, "Comedy") for item in comedy_raw]
    music_events = [_normalize_ticketmaster_event(item, "Music") for item in music_raw]

    return render(request, "booking/events.html", {
        "comedy_events": comedy_events,
        "music_events": music_events,
        "q": q,
        "country": country,
    })


def event_detail(request, slug): #To open a full event page.
    payload = _ticketmaster_get(f"/events/{slug}.json")

    if not payload:
        return render(request, "booking/event_detail.html", {
            "event": None
        })

    classifications = payload.get("classifications", [])
    category = "Event"
    if classifications:
        segment = classifications[0].get("segment", {}).get("name", "")
        genre = classifications[0].get("genre", {}).get("name", "")
        category = genre or segment or "Event"

    event = _normalize_ticketmaster_event(payload, category)

    return render(request, "booking/event_detail.html", {
        "event": event
    })