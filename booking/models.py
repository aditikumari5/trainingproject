from django.db import models
from django.contrib.auth.models import User


class Movie(models.Model):
    title = models.CharField(max_length=200)
    overview = models.TextField(blank=True, default="")
    poster_path = models.CharField(max_length=300, blank=True, default="")
    backdrop_path = models.CharField(max_length=300, blank=True, default="")
    release_date = models.DateField(null=True, blank=True)
    duration = models.IntegerField(default=0)
    rating = models.FloatField(default=0)
    vote_count = models.IntegerField(default=0)
    genre = models.CharField(max_length=255, blank=True, default="")
    tmdb_id = models.IntegerField(null=True, blank=True, unique=True)
    budget_level = models.CharField(max_length=20, default="medium")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Show(models.Model):
    movie_name = models.CharField(max_length=200)
    show_time = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

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
        return f"{self.seat_number} ({self.show.movie_name})"


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

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
        return f"{self.movie_name} - {self.seats}"


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "movie")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.movie.title}"
    

class ContinueWatching(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE
    )

    watched_seconds = models.IntegerField(
        default=0
    )

    completed = models.BooleanField(
        default=False
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.movie.title}"
    
trailer_url = models.URLField(
    blank=True,
    null=True
)