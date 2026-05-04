from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# Create your models here.
class Movie(models.Model):
    name = models.CharField(max_length=100)
    duration = models.IntegerField()
    genre = models.CharField(max_length= 50)

    def __str__(self):
        return self.name

class Theater(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length= 200)

    def __str__(self):
        return self.name

class Screen(models.Model):
    theater = models.ForeignKey(Theater, on_delete= models.CASCADE)
    screen_number = models.IntegerField()

    def __str__(self):
        return f"Screen {self.screen_number}"
    

class Show(models.Model):

    movie_name = models.CharField(max_length=100)

    show_time = models.TimeField()

    created_at = models.DateTimeField(
        default=timezone.now
    )

    def __str__(self):
        return f"{self.movie_name} - {self.show_time}"
class Seat(models.Model):

    seat_number = models.CharField(
        max_length=10
    )

    is_booked = models.BooleanField(
        default=False
    )

    show = models.ForeignKey(
        Show,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.seat_number
class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seats = models.ManyToManyField(Seat)
    booking_time = models.DateTimeField(auto_now_add= True)

    def __str__(self):
        return f"{self.user.username} Booking"
    
