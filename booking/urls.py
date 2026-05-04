from django.urls import path
from .views import (
    otp_login,
    verify_otp,
    signup_view,
    logout_view,
    show_seats,
    book_seat,
    book_multiple,
    payment_view,
    success_view,
    my_bookings,
    movies
)

urlpatterns = [

    # OTP Authentication
    path('', otp_login),
    path('login/', otp_login),
    path('verify-otp/', verify_otp),
    path('signup/', signup_view),
    path('logout/', logout_view),

    # Booking
    path('seats/', show_seats),
    path('book/<int:seat_id>/', book_seat),
    path('book-multiple/', book_multiple),

    # Payment
    path('payment/', payment_view),
    path('success/', success_view),

    # History
    path('my-bookings/', my_bookings),

    #Movies
    path('movies/', movies, name='movies'),
]