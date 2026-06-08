from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib import admin


#------------------
#PAYMENT MODEL
#--------------------
class Payment(models.Model):
    booking = models.ForeignKey(
    'booking.Booking',
    on_delete=models.CASCADE
)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} - {self.status}"

#------------------
#MOVIE MODEL
#--------------------
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
    language = models.CharField(max_length=50,blank=True,default="")

    def __str__(self):
        return self.title


#------------------
#SHOW MODEL
#--------------------
class Show(models.Model):
    movie_name = models.CharField(max_length=200)
    show_time = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.movie_name} - {self.show_time}"


#------------------
#SEAT MODEL
#--------------------
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


#------------------
#BOOKING MODEL
#--------------------
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
    is_ticket_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.movie_name} - {self.seats}"


#------------------
#WISHLIST MODEL
#--------------------
class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "movie")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.movie.title}"
    

#-------------------------
# CONTINUE WATCHING  MODEL
#-------------------------
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



#------------------
#FOOD COMBO OFFER MODEL
#--------------------
class ComboOffer(models.Model):
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    original_price = models.DecimalField(max_digits=8, decimal_places=2)
    offer_price = models.DecimalField(max_digits=8, decimal_places=2)
    image_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title
    


#------------------
# FOOD ITEM MODEL
#--------------------

class FoodItem(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image_url = models.URLField(blank=True, null=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.name


#------------------
# FOOD CART ITEM MODEL
#--------------------
class FoodCartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return self.quantity * self.food_item.price

    def __str__(self):
        return f"{self.user.username} - {self.food_item.name} x {self.quantity}"
    

#------------------
#EVENT MODEL
#--------------------
class Event(models.Model):
    EVENT_TYPE_CHOICES = [
        ("COMEDY", "Comedy"),
        ("MUSIC", "Music"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(
    unique=True,
    blank=True,
    null=True
)

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES
    )

    description = models.TextField(
        blank=True,
        default=""
    )

    poster_path = models.CharField(
        max_length=500,
        blank=True,
        default=""
    )

    date = models.DateField(
        null=True,
        blank=True
    )

    time = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    venue = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    price = models.IntegerField(
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.title

#------------------
#SUPPORT TICKET MODEL
#--------------------

class SupportTicket(models.Model):
    CATEGORY_CHOICES = [
        ("BOOKING", "Booking Issue"),
        ("PAYMENT", "Payment Issue"),
        ("OTHER", "Other Issue"),
    ]

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.get_category_display()} - {self.status}"
    


#------------------
#SUPPORT TICKET ADMIN MODEL
#--------------------
@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "status", "created_at")
    list_filter = ("category", "status", "created_at")
    search_fields = ("name", "email", "message")
    readonly_fields = ("created_at", "updated_at")