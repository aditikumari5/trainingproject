import hashlib
import hmac
import io
import random
from datetime import datetime, timedelta

import qrcode
import razorpay
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import FileResponse, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .models import Booking, Movie, Seat, Show


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


def send_otp_email(receiver_email, otp):
    try:
        send_mail(
            "ShowTime OTP Verification",
            f"Your OTP is {otp}",
            getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
            [receiver_email],
            fail_silently=False,
        )
        print("EMAIL SENT SUCCESSFULLY")
    except Exception as e:
        print("MAIL ERROR:", e)


def send_booking_confirmation_email(user_email, booking):
    if not user_email:
        return

    subject = f"ShowTime Booking Confirmed - {booking.movie_name}"

    message = f"""
Hello,

Your booking has been confirmed successfully.

Movie: {booking.movie_name}
Show Time: {booking.show_time}
Seats: {booking.seats}
Amount: ₹{booking.amount}
Payment Method: {booking.payment_method}
Booking Time: {booking.booked_at}

Thank you for booking with ShowTime.
"""

    try:
        send_mail(
            subject,
            message,
            getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
            [user_email],
            fail_silently=False,
        )
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


# ---------------------------
# SIGNUP
# ---------------------------

def signup_view(request):
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
        request.session["signup_otp"] = str(otp)
        request.session["signup_user_id"] = user.id

        send_otp_email(email, otp)
        return redirect("/verify-signup-otp/")

    return render(request, "booking/signup.html")


def signup_otp(request):
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


# ---------------------------
# OTP LOGIN
# ---------------------------

def otp_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        user = User.objects.filter(email=email).first()

        if not user:
            return render(request, "booking/otp_login.html", {"error": "Email not registered"})

        otp = random.randint(100000, 999999)
        request.session["otp"] = str(otp)
        request.session["user_id"] = user.id

        send_otp_email(user.email, otp)
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


# ---------------------------
# LOGOUT
# ---------------------------

def logout_view(request):
    logout(request)
    return redirect("/")


# ---------------------------
# HOME / MOVIES
# ---------------------------

def home(request):
    movies = Movie.objects.filter(is_active=True).order_by("-release_date")
    return render(request, "booking/home.html", {"movies": movies})


def movies(request):
    movies = Movie.objects.filter(is_active=True).order_by("-release_date")

    query = request.GET.get("q", "").strip()
    genre = request.GET.get("genre", "").strip()

    if query:
        movies = movies.filter(title__icontains=query)

    if genre:
        movies = movies.filter(genre__icontains=genre)

    all_genres = [
        "Action", "Comedy", "Drama", "Horror", "Romance",
        "Thriller", "Sci-Fi", "Adventure", "Animation", "Fantasy"
    ]

    return render(
        request,
        "booking/movies.html",
        {
            "movies": movies,
            "query": query,
            "selected_genre": genre,
            "all_genres": all_genres,
        },
    )


# ---------------------------
# MOVIE DETAILS
# ---------------------------

@login_required
def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id, is_active=True)

    trailer_key = None
    trailer_url = get_youtube_trailer_url(movie.title)

    tmdb_api_key = getattr(settings, "TMDB_API_KEY", None)

    if tmdb_api_key and movie.tmdb_id:
        videos_url = f"https://api.themoviedb.org/3/movie/{movie.tmdb_id}/videos"
        params = {
            "api_key": tmdb_api_key,
            "language": "en-US",
        }

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
# SHOW TIMINGS
# ---------------------------

@login_required
def show_timings(request):
    movie_id = request.GET.get("movie_id")

    if not movie_id:
        return redirect("/movies/")

    movie = get_object_or_404(Movie, id=movie_id, is_active=True)

    shows = Show.objects.filter(movie_name__iexact=movie.title).order_by("show_time")

    if not shows.exists():
        default_times = ["10:00:00", "14:00:00", "18:00:00"]

        for time_str in default_times:
            show = Show.objects.create(
                movie_name=movie.title,
                show_time=time_str,
            )
            ensure_seats_for_show(show)

        shows = Show.objects.filter(movie_name__iexact=movie.title).order_by("show_time")
    else:
        for show in shows:
            ensure_seats_for_show(show)

    return render(
        request,
        "booking/show_timings.html",
        {
            "movie": movie.title,
            "shows": shows,
        },
    )


# ---------------------------
# SEATS
# ---------------------------

@login_required
def show_seats(request):
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
            "seats": seats,
            "movie": show.movie_name,
            "show_time": show.show_time,
            "now": timezone.now(),
        },
    )


@login_required
def book_seat(request, seat_id):
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
def book_multiple(request):
    if request.method != "POST":
        return redirect("/seats/")

    seat_ids = request.POST.getlist("seats")

    if not seat_ids:
        return redirect("/seats/")

    release_expired_locks()

    with transaction.atomic():
        selected_seats = Seat.objects.select_for_update().filter(id__in=seat_ids)

        if not selected_seats.exists():
            return redirect("/seats/")

        if selected_seats.values("show").distinct().count() != 1:
            return HttpResponseBadRequest("Selected seats must belong to the same show")

        if selected_seats.filter(is_booked=True).exists():
            return HttpResponse("One or more selected seats are already booked")

        if selected_seats.filter(is_locked=True).exists():
            return HttpResponse("One or more selected seats are temporarily locked")

        show = selected_seats.first().show

        lock_owner = request.session.session_key
        if not lock_owner:
            request.session.create()
            lock_owner = request.session.session_key

        expires_at = lock_seats(selected_seats, lock_owner, minutes=5)

        request.session["booked_seats"] = seat_ids
        request.session["show_id"] = show.id
        request.session["movie_name"] = show.movie_name
        request.session["show_time"] = str(show.show_time)
        request.session["seats"] = ", ".join(seat.seat_number for seat in selected_seats)
        request.session["amount"] = sum(seat.price for seat in selected_seats)
        request.session["lock_expires_at"] = expires_at.isoformat()

    return redirect("/payment/")


# ---------------------------
# PAYMENT
# ---------------------------

@login_required
def payment_view(request):
    release_expired_locks()

    movie_name = request.session.get("movie_name", "Unknown Movie")
    show_time = request.session.get("show_time", "Unknown Time")
    seats = request.session.get("seats", "N/A")
    amount = int(request.session.get("amount", 500))
    lock_expires_at = request.session.get("lock_expires_at")

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

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    order = client.order.create({
        "amount": amount * 100,
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
            "amount": amount,
            "movie_name": movie_name,
            "show_time": show_time,
            "seats": seats,
            "lock_expires_at": lock_expires_at,
        },
    )


@csrf_exempt
@login_required
def payment_success(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request")

    razorpay_payment_id = request.POST.get("razorpay_payment_id")
    razorpay_order_id = request.POST.get("razorpay_order_id")
    razorpay_signature = request.POST.get("razorpay_signature")

    if not razorpay_payment_id or not razorpay_order_id or not razorpay_signature:
        return HttpResponseBadRequest("Missing payment details")

    generated_signature = hmac.new(
        key=settings.RAZORPAY_KEY_SECRET.encode(),
        msg=f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(generated_signature, razorpay_signature):
        return HttpResponseBadRequest("Payment signature verification failed")

    seat_ids = request.session.get("booked_seats", [])
    if not seat_ids:
        return HttpResponseBadRequest("No seats found in session")

    with transaction.atomic():
        selected_seats = Seat.objects.select_for_update().filter(id__in=seat_ids)

        if selected_seats.count() != len(seat_ids):
            return HttpResponseBadRequest("Some seats are missing")

        if selected_seats.filter(is_booked=True).exists():
            return HttpResponse("One or more seats are already booked")

        for seat in selected_seats:
            seat.is_booked = True
            seat.is_locked = False
            seat.locked_by = ""
            seat.locked_at = None
            seat.lock_expires_at = None
            seat.save()

        booking = Booking.objects.create(
            user=request.user,
            movie_name=request.session.get("movie_name", "Unknown Movie"),
            show_time=request.session.get("show_time", "Unknown Time"),
            seats=request.session.get("seats", "N/A"),
            amount=int(request.session.get("amount", 500)),
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            payment_status=True,
            payment_method="Online",
        )

    send_booking_confirmation_email(request.user.email, booking)

    request.session.pop("booked_seats", None)
    request.session.pop("show_id", None)
    request.session.pop("movie_name", None)
    request.session.pop("show_time", None)
    request.session.pop("seats", None)
    request.session.pop("amount", None)
    request.session.pop("razorpay_order_id", None)
    request.session.pop("lock_expires_at", None)

    return render(request, "booking/thank_you.html", {"booking": booking})


@login_required
def cash_payment_success(request):
    if request.method != "POST":
        return redirect("/payment/")

    seat_ids = request.session.get("booked_seats", [])
    if not seat_ids:
        return redirect("/seats/")

    with transaction.atomic():
        selected_seats = Seat.objects.select_for_update().filter(id__in=seat_ids)

        if selected_seats.count() != len(seat_ids):
            return HttpResponse("Some seats are missing")

        if selected_seats.filter(is_booked=True).exists():
            return HttpResponse("One or more seats are already booked")

        for seat in selected_seats:
            seat.is_booked = True
            seat.is_locked = False
            seat.locked_by = ""
            seat.locked_at = None
            seat.lock_expires_at = None
            seat.save()

        booking = Booking.objects.create(
            user=request.user,
            movie_name=request.session.get("movie_name", "Unknown Movie"),
            show_time=request.session.get("show_time", "Unknown Time"),
            seats=request.session.get("seats", "N/A"),
            amount=int(request.session.get("amount", 500)),
            razorpay_order_id="CASH",
            razorpay_payment_id="CASH",
            payment_status=True,
            payment_method="Cash",
        )

    send_booking_confirmation_email(request.user.email, booking)

    request.session.pop("booked_seats", None)
    request.session.pop("show_id", None)
    request.session.pop("movie_name", None)
    request.session.pop("show_time", None)
    request.session.pop("seats", None)
    request.session.pop("amount", None)
    request.session.pop("razorpay_order_id", None)
    request.session.pop("lock_expires_at", None)

    return render(request, "booking/thank_you.html", {"booking": booking})


# ---------------------------
# HISTORY
# ---------------------------

@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(
        user=request.user
    ).order_by("-booked_at")

    return render(
        request,
        "booking/history.html",
        {"bookings": bookings}
    )

# ---------------------------
# PDF TICKET
# ---------------------------

@login_required
def download_ticket_pdf(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if not request.user.is_staff and booking.user_id != request.user.id:
        return HttpResponseForbidden("You are not allowed to download this ticket.")

    qr_data = (
        f"Booking ID: {booking.id}\n"
        f"Movie: {booking.movie_name}\n"
        f"Show Time: {booking.show_time}\n"
        f"Seats: {booking.seats}\n"
        f"Amount: ₹{booking.amount}\n"
        f"Payment Method: {booking.payment_method}"
    )

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
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

    p.setFont("Helvetica-Bold", 26)
    p.drawString(170, 750, "ShowTime Ticket")
    p.line(50, 730, 560, 730)

    p.setFont("Helvetica", 16)

    details = [
        f"Booking ID: #{booking.id}",
        f"Movie: {booking.movie_name}",
        f"Show Time: {booking.show_time}",
        f"Seats: {booking.seats}",
        f"Amount Paid: ₹{booking.amount}",
        f"Payment Method: {booking.payment_method}",
        f"Booking Date: {booking.booked_at.strftime('%d %b %Y %I:%M %p')}",
    ]

    y = 680
    for detail in details:
        p.drawString(70, y, detail)
        y -= 35

    qr_reader = ImageReader(qr_buffer)
    p.drawImage(qr_reader, 380, 470, width=120, height=120, mask="auto")

    p.setFont("Helvetica-Bold", 12)
    p.drawString(395, 455, "SCAN QR AT ENTRY")

    p.setFont("Helvetica-Oblique", 12)
    p.drawString(150, 120, "Thank you for booking with ShowTime 🎬")

    p.showPage()
    p.save()

    buffer.seek(0)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"ticket_{booking.id}.pdf",
    )


# ---------------------------
# DASHBOARD / ADMIN
# ---------------------------

@staff_member_required
def admin_dashboard(request):
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
def admin_movies(request):
    movies = Movie.objects.all().order_by("-id")
    return render(request, "booking/admin_movies.html", {"movies": movies})


@staff_member_required
def admin_add_movie(request):
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
def admin_delete_movie(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    movie.delete()
    return redirect("/admin-movies/")


@staff_member_required
def admin_shows(request):
    shows = Show.objects.all().order_by("-id")
    movies = Movie.objects.filter(is_active=True).order_by("title")
    return render(
        request,
        "booking/admin_shows.html",
        {
            "shows": shows,
            "movies": movies,
        },
    )


@staff_member_required
def admin_add_show(request):
    movies = Movie.objects.filter(is_active=True).order_by("title")

    if request.method == "POST":
        movie_id = request.POST.get("movie_id")
        show_time = request.POST.get("show_time")

        movie = get_object_or_404(Movie, id=movie_id, is_active=True)

        show = Show.objects.create(
            movie_name=movie.title,
            show_time=show_time,
        )
        ensure_seats_for_show(show)

        return redirect("/admin-shows/")

    return render(request, "booking/admin_add_show.html", {"movies": movies})


@staff_member_required
def admin_delete_show(request, show_id):
    show = get_object_or_404(Show, id=show_id)
    show.delete()
    return redirect("/admin-shows/")


@staff_member_required
def admin_bookings(request):
    bookings = Booking.objects.all().order_by("-booked_at")

    total_earnings = Booking.objects.filter(payment_status=True).aggregate(
        total=Sum("amount")
    )["total"] or 0

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

    return render(
        request,
        "booking/admin_bookings.html",
        {
            "bookings": bookings,
            "total_earnings": total_earnings,
            "total_bookings": total_bookings,
            "top_movies": top_movies_qs,
            "top_movies_labels": top_movies_labels,
            "top_movies_counts": top_movies_counts,
            "daily_labels": daily_labels,
            "daily_earnings": daily_earnings,
        },
    )


# ---------------------------
# AI RECOMMENDATION
# ---------------------------

@login_required
def ai_recommend(request):
    query = request.GET.get("q", "").strip().lower()
    movies = Movie.objects.filter(is_active=True)
    recommended = []

    if query:
        for movie in movies:
            genre = (movie.genre or "").lower()
            title = (movie.title or "").lower()
            overview = (movie.overview or "").lower()

            if query in genre or query in title or query in overview:
                recommended.append(movie)
    else:
        recommended = movies.order_by("-rating", "-vote_count")[:8]

    return render(
        request,
        "booking/ai_recommend.html",
        {
            "query": query,
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

    if request.user.is_staff:
        booking = get_object_or_404(Booking, id=booking_id)
    else:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    with transaction.atomic():
        release_seats_for_booking(booking)
        booking.delete()

    messages.success(request, "Booking cancelled successfully.")
    return redirect("/my-bookings/")