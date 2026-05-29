from django.contrib import admin
from .models import (
    Movie,
    Show,
    Seat,
    Booking,
    Payment,
    Wishlist,
    ContinueWatching,
    ComboOffer,
    FoodItem,
    FoodCartItem,
    Event,
)

admin.site.register(Movie)
admin.site.register(Show)
admin.site.register(Seat)
admin.site.register(Booking)
admin.site.register(Payment)
admin.site.register(Wishlist)
admin.site.register(ContinueWatching)
admin.site.register(ComboOffer)
admin.site.register(FoodItem)
admin.site.register(FoodCartItem)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "event_type",
        "date",
        "time",
        "venue",
        "price",
        "is_active",
    )
    list_filter = ("event_type", "is_active")
    search_fields = ("title", "venue", "description")