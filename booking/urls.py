from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("movies/", views.movies, name="movies"),

    path("signup/", views.signup_view, name="signup"),
    path("verify-signup-otp/", views.signup_otp, name="verify_signup_otp"),

    path("otp-login/", views.otp_login, name="otp_login"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),

    path("logout/", views.logout_view, name="logout"),

    path("movie/<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path("shows/", views.show_timings, name="show_timings"),
    path("seats/", views.show_seats, name="show_seats"),

    path("book-multiple/", views.book_multiple, name="book_multiple"),

    path("payment/", views.payment_view, name="payment"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("payment/cash/", views.cash_payment_success, name="cash_payment_success"),

    path("my-bookings/", views.my_bookings, name="my_bookings"),

    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-movies/", views.admin_movies, name="admin_movies"),
    path("admin-movies/add/", views.admin_add_movie, name="admin_add_movie"),
    path("admin-movies/delete/<int:movie_id>/", views.admin_delete_movie, name="admin_delete_movie"),
    path("admin-bookings/", views.admin_bookings, name="admin_bookings"),
    path("ticket/<int:booking_id>/pdf/", views.download_ticket_pdf, name="download_ticket_pdf"),
    path("ticket/<int:booking_id>/", views.download_ticket_pdf, name="download_ticket"),
    path("ai-recommend/", views.ai_recommend, name="ai_recommend"),
    path("booking/cancel/<int:booking_id>/", views.cancel_booking, name="cancel_booking"),
    

]