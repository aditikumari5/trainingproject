from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone




class Movie(models.Model):
    tmdb_id = models.IntegerField(unique=True, null=True, blank=True)
    title = models.CharField(max_length=255, default="")
    overview = models.TextField(blank=True, default="")
    poster_path = models.CharField(max_length=500, blank=True, default="")
    backdrop_path = models.CharField(max_length=500, blank=True, default="")
    release_date = models.DateField(null=True, blank=True)
    duration = models.PositiveIntegerField(default=0)
    rating = models.FloatField(default=0)
    vote_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    genre = models.CharField(max_length=200, blank=True, default="")
    budget_level = models.CharField(max_length=20, blank=True, default="")

    def __str__(self):
        return self.title


class Theater(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Screen(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)
    screen_number = models.IntegerField()

    def __str__(self):
        return f"Screen {self.screen_number}"


class Show(models.Model):
    movie_name = models.CharField(max_length=100)
    show_time = models.TimeField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.movie_name} - {self.show_time}"


class Seat(models.Model):
    seat_number = models.CharField(max_length=10)
    is_booked = models.BooleanField(default=False)

    is_locked = models.BooleanField(default=False)
    locked_by = models.CharField(max_length=100, blank=True, default="")
    locked_at = models.DateTimeField(null=True, blank=True)
    lock_expires_at = models.DateTimeField(null=True, blank=True)

    price = models.IntegerField(default=150)
    show = models.ForeignKey(Show, on_delete=models.CASCADE)

    def __str__(self):
        return self.seat_number

class Booking(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    movie_name = models.CharField(max_length=200)
    show_time = models.CharField(max_length=100)
    seats = models.CharField(max_length=200)

    amount = models.IntegerField(default=0)

    razorpay_order_id = models.CharField(max_length=200)
    razorpay_payment_id = models.CharField(max_length=200)

    payment_status = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=50)

    booked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.movie_name
