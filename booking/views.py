from datetime import datetime, timedelta
import json
import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from reportlab.pdfgen import canvas

import razorpay

from .models import (
    Booking,
    Movie,
    Seat,
    Show,
    Wishlist,
)


# =====================================
# HOME
# =====================================

def home(request):

    trending_movies = Movie.objects.filter(
        is_active=True
    ).order_by(
        "-rating",
        "-vote_count"
    )[:8]

    return render(
        request,
        "booking/home.html",
        {
            "trending_movies": trending_movies
        }
    )


# =====================================
# MOVIES
# =====================================

def movies(request):

    query = request.GET.get("q", "")
    selected_genre = request.GET.get("genre", "")

    movies = Movie.objects.filter(
        is_active=True
    )

    if query:

        movies = movies.filter(
            Q(title__icontains=query)
            |
            Q(genre__icontains=query)
        )

    if selected_genre:

        movies = movies.filter(
            genre__icontains=selected_genre
        )

    all_genres = []

    genre_movies = Movie.objects.exclude(
        genre=""
    )

    for movie in genre_movies:

        genres = movie.genre.split(",")

        for g in genres:

            g = g.strip()

            if g and g not in all_genres:
                all_genres.append(g)

    all_genres.sort()

    return render(
        request,
        "booking/movies.html",
        {
            "movies": movies,
            "query": query,
            "selected_genre": selected_genre,
            "all_genres": all_genres,
        },
    )


# =====================================
# MOVIE DETAIL
# =====================================

def movie_detail(request, movie_id):

    movie = get_object_or_404(
        Movie,
        id=movie_id,
        is_active=True
    )

    trailer_url = None

    return render(
        request,
        "booking/movie_detail.html",
        {
            "movie": movie,
            "trailer_url": trailer_url,
        },
    )


# =====================================
# SHOW TIMINGS
# =====================================

def show_timings(request):

    movie_id = request.GET.get("movie_id")

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    timings = [
        "10:00 AM",
        "1:00 PM",
        "4:00 PM",
        "7:00 PM",
        "10:00 PM",
    ]

    return render(
        request,
        "booking/show_timings.html",
        {
            "movie": movie,
            "timings": timings,
        },
    )


# =====================================
# SHOW SEATS
# =====================================

@login_required
def show_seats(request):

    movie_name = request.GET.get("movie")
    show_time = request.GET.get("time")

    rows = ["A", "B", "C", "D", "E"]
    cols = range(1, 9)

    all_seats = []

    for row in rows:

        for col in cols:

            seat_number = f"{row}{col}"

            all_seats.append(
                {
                    "seat_number": seat_number,
                    "price": 150,
                }
            )

    return render(
        request,
        "booking/seats.html",
        {
            "movie": movie_name,
            "show_time": show_time,
            "all_seats": all_seats,
        },
    )


# =====================================
# BOOK MULTIPLE
# =====================================

@login_required
def book_multiple(request):

    if request.method != "POST":
        return redirect("/movies/")

    selected_seats = request.POST.getlist(
        "selected_seats"
    )

    if not selected_seats:

        messages.error(
            request,
            "Please select at least one seat."
        )

        return redirect(
            request.META.get(
                "HTTP_REFERER",
                "/movies/"
            )
        )

    request.session["movie_name"] = request.POST.get(
        "movie"
    )

    request.session["show_time"] = request.POST.get(
        "show_time"
    )

    request.session["selected_seats"] = selected_seats

    amount = len(selected_seats) * 150

    request.session["amount"] = amount

    return redirect("/payment/")


# =====================================
# PAYMENT PAGE
# =====================================

@login_required
def payment_view(request):

    movie_name = request.session.get(
        "movie_name"
    )

    show_time = request.session.get(
        "show_time"
    )

    seats = request.session.get(
        "selected_seats"
    )

    amount = request.session.get(
        "amount"
    )

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )

    payment_data = {
        "amount": amount * 100,
        "currency": "INR",
        "payment_capture": 1,
    }

    order = client.order.create(
        data=payment_data
    )

    request.session[
        "razorpay_order_id"
    ] = order["id"]

    return render(
        request,
        "booking/payment.html",
        {
            "movie_name": movie_name,
            "show_time": show_time,
            "seats": ", ".join(seats),
            "amount": amount,
            "order_id": order["id"],
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        },
    )


# =====================================
# PAYMENT SUCCESS
# =====================================

@login_required
@csrf_exempt
def payment_success(request):

    if request.method != "POST":
        return redirect("/movies/")

    booking = Booking.objects.create(
        user=request.user,
        movie_name=request.session.get(
            "movie_name"
        ),
        show_time=request.session.get(
            "show_time"
        ),
        seats=", ".join(
            request.session.get(
                "selected_seats",
                []
            )
        ),
        amount=request.session.get(
            "amount"
        ),
        razorpay_order_id=request.POST.get(
            "razorpay_order_id"
        ),
        razorpay_payment_id=request.POST.get(
            "razorpay_payment_id"
        ),
        payment_status=True,
        payment_method="Online",
    )

    return render(
        request,
        "booking/thank_you.html",
        {
            "booking": booking
        },
    )


# =====================================
# CASH PAYMENT SUCCESS
# =====================================

@login_required
def cash_payment_success(request):

    booking = Booking.objects.create(
        user=request.user,
        movie_name=request.session.get(
            "movie_name"
        ),
        show_time=request.session.get(
            "show_time"
        ),
        seats=", ".join(
            request.session.get(
                "selected_seats",
                []
            )
        ),
        amount=request.session.get(
            "amount"
        ),
        razorpay_order_id="CASH",
        razorpay_payment_id="CASH",
        payment_status=True,
        payment_method="Cash",
    )

    return render(
        request,
        "booking/thank_you.html",
        {
            "booking": booking
        },
    )


# =====================================
# DOWNLOAD PDF
# =====================================

@login_required
def download_ticket_pdf(
    request,
    booking_id
):

    booking = get_object_or_404(
        Booking,
        id=booking_id
    )

    response = HttpResponse(
        content_type="application/pdf"
    )

    response[
        "Content-Disposition"
    ] = f'attachment; filename="ticket_{booking.id}.pdf"'

    p = canvas.Canvas(response)

    p.setFont(
        "Helvetica-Bold",
        20
    )

    p.drawString(
        180,
        800,
        "ShowTime Movie Ticket"
    )

    p.setFont(
        "Helvetica",
        14
    )

    p.drawString(
        100,
        730,
        f"Movie: {booking.movie_name}"
    )

    p.drawString(
        100,
        690,
        f"Show Time: {booking.show_time}"
    )

    p.drawString(
        100,
        650,
        f"Seats: {booking.seats}"
    )

    p.drawString(
        100,
        610,
        f"Amount: ₹{booking.amount}"
    )

    p.drawString(
        100,
        570,
        f"Payment Method: {booking.payment_method}"
    )

    p.drawString(
        100,
        530,
        f"Booking ID: #{booking.id}"
    )

    p.showPage()
    p.save()

    return response


# =====================================
# MY BOOKINGS
# =====================================

@login_required
def my_bookings(request):

    bookings = Booking.objects.filter(
        user=request.user
    ).order_by(
        "-booked_at"
    )

    return render(
        request,
        "booking/history.html",
        {
            "bookings": bookings
        },
    )


# =====================================
# CANCEL BOOKING
# =====================================

@login_required
def cancel_booking(
    request,
    booking_id
):

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user,
    )

    booking.delete()

    messages.success(
        request,
        "Booking cancelled successfully."
    )

    return redirect("/my-bookings/")


# =====================================
# TRENDING DETECTION
# =====================================

def get_trending_movies():

    recent_days = (
        timezone.now()
        - timedelta(days=7)
    )

    trending_scores = {}

    movies = Movie.objects.filter(
        is_active=True
    )

    for movie in movies:

        score = 0

        rating = float(
            movie.rating or 0
        )

        score += rating * 10

        votes = int(
            movie.vote_count or 0
        )

        score += min(
            votes / 100,
            25
        )

        recent_bookings = Booking.objects.filter(
            movie_name=movie.title,
            booked_at__gte=recent_days
        ).count()

        score += recent_bookings * 15

        try:

            if movie.release_date:

                if isinstance(
                    movie.release_date,
                    str
                ):

                    release_date = datetime.fromisoformat(
                        movie.release_date
                    ).date()

                else:

                    release_date = movie.release_date

                days_old = (
                    timezone.localdate()
                    - release_date
                ).days

                if days_old <= 30:
                    score += 25

                elif days_old <= 90:
                    score += 10

        except Exception:
            pass

        trending_scores[movie.id] = score

    trending_movies = sorted(
        movies,
        key=lambda m: trending_scores.get(
            m.id,
            0
        ),
        reverse=True
    )

    return trending_movies[:10]


# =====================================
# AI RECOMMEND
# =====================================

def ai_recommend(request):

    query = request.GET.get("q", "")
    budget = request.GET.get("budget", "")
    genre_filter = request.GET.get("genre", "")
    min_rating = request.GET.get("min_rating", "")
    sort_by = request.GET.get("sort_by", "")

    movies = Movie.objects.filter(
        is_active=True
    )

    if query:

        movies = movies.filter(
            Q(title__icontains=query)
            |
            Q(genre__icontains=query)
            |
            Q(overview__icontains=query)
        )

    if budget:

        movies = movies.filter(
            budget_level=budget
        )

    if genre_filter:

        movies = movies.filter(
            genre__icontains=genre_filter
        )

    if min_rating:

        movies = movies.filter(
            rating__gte=float(min_rating)
        )

    if sort_by == "rating":

        movies = movies.order_by(
            "-rating"
        )

    elif sort_by == "votes":

        movies = movies.order_by(
            "-vote_count"
        )

    elif sort_by == "title":

        movies = movies.order_by(
            "title"
        )

    trending_movies = get_trending_movies()

    trending_ids = [
        tm.id for tm in trending_movies
    ]

    recommended = []

    for movie in movies:

        score = 0

        reasons = []

        if movie.id in trending_ids:

            trend_position = (
                trending_ids.index(movie.id) + 1
            )

            score += max(
                40 - trend_position * 3,
                10
            )

            reasons.append(
                "Trending Now"
            )

        score += movie.rating * 10

        if movie.vote_count > 1000:

            score += 20

            reasons.append(
                "Popular"
            )

        if budget and movie.budget_level == budget:

            score += 15

            reasons.append(
                "Budget Match"
            )

        if genre_filter and genre_filter.lower() in movie.genre.lower():

            score += 20

            reasons.append(
                "Genre Match"
            )

        recommended.append(
            {
                "movie": movie,
                "score": round(score),
                "reasons": reasons,
            }
        )

    recommended.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    preferred_genres = []

    if request.user.is_authenticated:

        bookings = Booking.objects.filter(
            user=request.user
        )

        genre_count = {}

        for booking in bookings:

            movie = Movie.objects.filter(
                title=booking.movie_name
            ).first()

            if movie and movie.genre:

                genres = movie.genre.split(",")

                for g in genres:

                    g = g.strip()

                    genre_count[g] = (
                        genre_count.get(g, 0) + 1
                    )

        preferred_genres = sorted(
            genre_count,
            key=genre_count.get,
            reverse=True
        )[:3]

    return render(
        request,
        "booking/ai_recommend.html",
        {
            "recommended": recommended,
            "query": query,
            "budget": budget,
            "genre_filter": genre_filter,
            "min_rating": min_rating,
            "sort_by": sort_by,
            "preferred_genres": preferred_genres,
            "trending_movies": trending_movies,
        },
    )


# =====================================
# WISHLIST
# =====================================

@login_required
def wishlist_page(request):

    wishlist_items = (
        Wishlist.objects.filter(
            user=request.user
        )
        .select_related("movie")
        .order_by("-created_at")
    )

    return render(
        request,
        "booking/wishlist.html",
        {
            "wishlist_items": wishlist_items,
        },
    )


@login_required
def add_to_wishlist(
    request,
    movie_id
):

    if request.method != "POST":
        return redirect("/movies/")

    movie = get_object_or_404(
        Movie,
        id=movie_id,
        is_active=True
    )

    Wishlist.objects.get_or_create(
        user=request.user,
        movie=movie
    )

    messages.success(
        request,
        f"{movie.title} added to wishlist ❤️"
    )

    return redirect(
        request.META.get(
            "HTTP_REFERER",
            "/movies/"
        )
    )


@login_required
def remove_from_wishlist(
    request,
    movie_id
):

    if request.method != "POST":
        return redirect("/wishlist/")

    movie = get_object_or_404(
        Movie,
        id=movie_id,
        is_active=True
    )

    Wishlist.objects.filter(
        user=request.user,
        movie=movie
    ).delete()

    messages.success(
        request,
        f"{movie.title} removed from wishlist."
    )

    return redirect(
        request.META.get(
            "HTTP_REFERER",
            "/wishlist/"
        )
    )


# =====================================
# AUTH
# =====================================

def signup_view(request):
    return render(
        request,
        "booking/signup.html"
    )


def signup_otp(request):
    return render(
        request,
        "booking/verify_signup_otp.html"
    )


def otp_login(request):
    return render(
        request,
        "booking/otp_login.html"
    )


def verify_otp(request):
    return render(
        request,
        "booking/verify_otp.html"
    )


def logout_view(request):

    logout(request)

    return redirect("/")


# =====================================
# ADMIN DASHBOARD
# =====================================

@login_required
def admin_dashboard(request):

    total_bookings = Booking.objects.count()

    total_revenue = (
        Booking.objects.aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )

    top_movies = (
        Booking.objects.values(
            "movie_name"
        )
        .annotate(
            total=Count("id")
        )
        .order_by("-total")[:5]
    )

    peak_shows = (
        Booking.objects.values(
            "show_time"
        )
        .annotate(
            total=Count("id")
        )
        .order_by("-total")[:5]
    )

    recent_bookings = Booking.objects.order_by(
        "-booked_at"
    )[:6]

    occupancy_percentage = random.randint(
        55,
        95
    )

    trending_movies_count = Movie.objects.filter(
        rating__gte=7.5
    ).count()

    return render(
        request,
        "booking/admin_dashboard.html",
        {
            "total_bookings": total_bookings,
            "total_revenue": total_revenue,
            "top_movies": top_movies,
            "peak_shows": peak_shows,
            "recent_bookings": recent_bookings,
            "occupancy_percentage": occupancy_percentage,
            "trending_movies_count": trending_movies_count,
        },
    )


@login_required
def admin_movies(request):

    movies = Movie.objects.all().order_by(
        "-id"
    )

    return render(
        request,
        "booking/admin_movies.html",
        {
            "movies": movies
        },
    )


@login_required
def admin_add_movie(request):

    return render(
        request,
        "booking/admin_add_movie.html"
    )


@login_required
def admin_delete_movie(
    request,
    movie_id
):

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    movie.delete()

    messages.success(
        request,
        "Movie deleted successfully."
    )

    return redirect("/admin-movies/")


@login_required
def admin_bookings(request):

    bookings = Booking.objects.order_by(
        "-booked_at"
    )

    return render(
        request,
        "booking/admin_bookings.html",
        {
            "bookings": bookings
        },
    )