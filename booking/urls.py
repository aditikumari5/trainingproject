from django.urls import path
from . import views

urlpatterns = [
    # ================= HOME =================
    path("", views.home, name="home"),
    path("movies/", views.movies, name="movies"),

    # ================= AUTH =================
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.otp_login, name="login"),
    path("verify-signup-otp/", views.signup_otp, name="verify_signup_otp"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("logout/", views.logout_view, name="logout"),

    # ================= MOVIES =================
    path("movie/<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path("shows/", views.show_timings, name="show_timings"),
    path("seats/", views.show_seats, name="show_seats"),

    # ================= BOOKING =================
    path("book-multiple/", views.book_multiple, name="book_multiple"),

    # ================= PAYMENT =================
    path("payment/", views.payment_view, name="payment"),

    path("payment/success/", views.payment_success, name="payment_success"),

    path("payment/cash/", views.cash_payment_success, name="cash_payment_success"),

    # ================= USER BOOKINGS =================
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("booking/cancel/<int:booking_id>/", views.cancel_booking, name="cancel_booking"),


    # ================= ADMIN =================
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-movies/", views.admin_movies, name="admin_movies"),
    path("admin-movies/add/", views.admin_add_movie, name="admin_add_movie"),
    path("admin-movies/delete/<int:movie_id>/", views.admin_delete_movie, name="admin_delete_movie"),
    path("admin-bookings/", views.admin_bookings, name="admin_bookings"),

    # ================= TICKETS =================
    path("ticket/<int:booking_id>/", views.download_ticket_pdf, name="download_ticket"),

    path("ticket/verify/<int:booking_id>/", views.verify_ticket, name="verify_ticket"),

    # ================= AI =================
    path("ai-recommend/", views.ai_recommend, name="ai_recommend"),
    path("chatbot-reply/", views.chatbot_reply, name="chatbot_reply"),

    # ================= WISHLIST =================
    path("wishlist/", views.wishlist_page, name="wishlist"),
    path("wishlist/add/<int:movie_id>/", views.add_to_wishlist, name="add_to_wishlist"),
    path("wishlist/remove/<int:movie_id>/", views.remove_from_wishlist, name="remove_from_wishlist"),

    # ================= FOOD OFFERS =================
    path("food-offers/", views.food_offers, name="food_offers"),
    path("food-cart/add/<int:food_id>/", views.add_food_to_cart, name="add_food_to_cart"),
    path("food-cart/remove/<int:food_id>/", views.remove_food_from_cart, name="remove_food_from_cart"),
    path("food-cart/update/<int:food_id>/<str:action>/", views.update_food_qty, name="update_food_qty"),
]