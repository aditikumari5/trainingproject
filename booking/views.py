from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.db import transaction
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail

from .models import Seat, Booking

import random
import requests
import razorpay
from django.conf import settings 



# ---------------------------
# SEND OTP EMAIL
# ---------------------------

def send_otp_email(receiver_email, otp):

    try:

        send_mail(
            'ShowTime OTP Verification',
            f'Your OTP is {otp}',
            'adi.juhi5@gmail.com',
            [receiver_email],
            fail_silently=False
        )

        print(
            "EMAIL SENT SUCCESSFULLY"
        )

    except Exception as e:

        print(
            "MAIL ERROR:",
            e
        )



# ---------------------------
# SIGNUP
# ---------------------------

def signup_view(request):

    if request.method == "POST":

        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Empty check
        if not username or not email or not password:
            return render(request, 'booking/signup.html',
                          {'error': 'All fields are required'})

        # Password strength check
        if len(password) < 6:
            return render(request, 'booking/signup.html',
                          {'error': 'Password must be at least 6 characters'})

        if not any(char.isdigit() for char in password):
            return render(request, 'booking/signup.html',
                          {'error': 'Password must contain a number'})

        # Duplicate checks
        if User.objects.filter(username=username).exists():
            return render(request, 'booking/signup.html',
                          {'error': 'Username already exists'})

        if User.objects.filter(email=email).exists():
            return render(request, 'booking/signup.html',
                          {'error': 'Email already registered'})

        # Create user BUT DO NOT LOGIN
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Generate OTP
        import random
        otp = random.randint(100000, 999999)

        request.session['signup_otp'] = str(otp)
        request.session['signup_user_id'] = user.id

        send_otp_email(email, otp)

        return redirect('/verify-signup-otp/')

    return render(request, 'booking/signup.html')

# VERIFY SIGNUP OTP
def signup_otp(request):

    if request.method == "POST":
        entered_otp = request.POST.get('otp')
        saved_otp = request.session.get('signup_otp')

        if entered_otp == saved_otp:
            user_id = request.session.get('signup_user_id')
            user = User.objects.get(id = user_id)

            login(request, user)

            request.session.pop('signup_otp', None)
            request.session.pop('signup_user_id', None)

            return redirect('/seats')
        
        return render(request, 'booking/verify_signup_otp.html', 
                      {
                          'error': 'Invalid OTP'
                      })
    return render(request, 'booling/verify_signup_otp.html')
    
# ---------------------------
# OTP LOGIN
# ---------------------------

def otp_login(request):

    if request.method == "POST":

        email = request.POST.get('email')

        # Get user safely (avoid MultipleObjectsReturned)
        user = User.objects.filter(email=email).first()

        if not user:
            return render(
                request,
                'booking/otp_login.html',
                {
                    'error': 'Email not registered'
                }
            )

        # Generate OTP
        import random
        otp = random.randint(100000, 999999)

        # Store in session
        request.session['otp'] = str(otp)
        request.session['user_id'] = user.id

        # Debug (optional)
        print("Sending OTP to:", user.email)
        print("OTP:", otp)

        # Send email
        send_otp_email(user.email, otp)

        return redirect('/verify-otp/')

    return render(
        request,
        'booking/otp_login.html'
    )


# ---------------------------
# VERIFY OTP
# ---------------------------

def verify_otp(request):

    if request.method=="POST":

        entered_otp=request.POST.get(
            'otp'
        )

        saved_otp=request.session.get(
            'otp'
        )


        if entered_otp==saved_otp:

            user_id=request.session.get(
                'user_id'
            )


            user=User.objects.get(
                id=user_id
            )


            login(
                request,
                user
            )


            request.session.pop(
                'otp',
                None
            )

            request.session.pop(
                'user_id',
                None
            )


            return redirect(
                '/seats/'
            )


        return render(
            request,
            'booking/verify_otp.html',
            {
             'error':
             'Invalid OTP'
            }
        )


    return render(
        request,
        'booking/verify_otp.html'
    )



# ---------------------------
# LOGOUT
# ---------------------------

def logout_view(request):

    logout(
        request
    )

    return redirect(
        '/'
    )



# ---------------------------
# HOME
# ---------------------------

def home(request):

    return HttpResponse(
        "Welcome To ShowTime"
    )



# ---------------------------
# SEATS
# ---------------------------

@login_required
def show_seats(request):

    movie = request.GET.get('movie')

    seats = Seat.objects.all()

    return render(
        request,
        'booking/seats.html',
        {
            'seats': seats,
            'movie': movie
        }
    )


# ---------------------------
# SINGLE SEAT
# ---------------------------

@login_required
def book_seat(request, seat_id):

    with transaction.atomic():

        seat=Seat.objects.select_for_update().get(
            id=seat_id
        )


        if seat.is_booked:

            return HttpResponse(
                "Seat already booked"
            )


        seat.is_booked=True

        seat.save()


    return HttpResponse(
        "Seat booked successfully"
    )



# ---------------------------
# MULTI SEAT
# ---------------------------

@login_required
def book_multiple(request):

    if request.method == "POST":

        seat_ids = request.POST.getlist('seats')

        print("Selected seats:", seat_ids)  # DEBUG

        if not seat_ids:
            return redirect('/seats/')

        request.session['booked_seats'] = seat_ids

        return redirect('/payment/')

    return redirect('/seats/')

# ---------------------------
# PAYMENT
# ---------------------------

@login_required
def payment_view(request):

    seat_ids = request.session.get('booked_seats', [])

    print("Session seats:", seat_ids)  # DEBUG

    if not seat_ids:
        return redirect('/seats/')

    seats = Seat.objects.filter(id__in=seat_ids)

    if not seats:
        return redirect('/seats/')

    show = seats.first().show

    hour = show.show_time.hour

    if hour < 12:
        price = 120
    elif hour < 17:
        price = 180
    else:
        price = 250

    total = len(seats) * price

    return render(
        request,
        'booking/payment.html',
        {
            'seats': seats,
            'total': total,
            'price_per_seat': price,
            'show': show
        }
    )
# ✔ Dynamic pricing based on movie
# ✔ No hardcoded ₹150 anymore
# ✔ Works with session movie
# ✔ Clean structure
# ✔ Ready for real payment integration later


# ---------------------------
# SUCCESS
# ---------------------------

@login_required
def success_view(request):

    seat_ids=request.session.get(
        'booked_seats',
        []
    )


    if not seat_ids:

        return redirect(
            '/seats/'
        )


    booked_successfully=[]
    already_booked=[]


    with transaction.atomic():

        seats=Seat.objects.select_for_update().filter(
            id__in=seat_ids
        )


        for seat in seats:

            if seat.is_booked:

                already_booked.append(
                    seat.seat_number
                )

            else:

                seat.is_booked=True
                seat.save()

                booked_successfully.append(
                    seat
                )


        if booked_successfully:

            booking=Booking.objects.create(
                user=request.user
            )

            booking.seats.set(
                booked_successfully
            )


    request.session[
        'booked_seats'
    ]=[]


    return render(
        request,
        'booking/success.html',
        {
          'seats':booked_successfully,
          'already_booked':already_booked
        }
    )



# ---------------------------
# HISTORY
# ---------------------------

@login_required
def my_bookings(request):

    bookings=Booking.objects.filter(
        user=request.user
    ).order_by(
        'booking_time'
    )


    return render(
        request,
        'booking/history.html',
        {
         'bookings':bookings
        }
    )



# ---------------------------
# MOVIES API
# ---------------------------

def movies(request):

    api_key='ceaf8173'


    titles=[
      'Dune',
      'Oppenheimer',
      'Avengers',
      'Mission Impossible',
      'Interstellar',
      'Dhurandhar',
      'Toxic',
      'Breaking Bad',
      'From',
      'Stranger Things',
      'The Vampire Diaries'
    ]


    movie_list=[]


    for title in titles:

        url=f'https://www.omdbapi.com/?t={title}&apikey={api_key}'

        r=requests.get(
            url
        )

        movie_list.append(
            r.json()
        )


    return render(
        request,
        'booking/movies.html',
        {
         'movies':movie_list
        }
    )