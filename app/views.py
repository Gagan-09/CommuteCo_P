from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib import messages
from .models import *
from datetime import datetime
from django.db.models import Q, Count
from django.urls import reverse
import json
import requests
from math import radians, sin, cos, sqrt, atan2
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from web3 import Web3
import socket

def calculate_distance(lat1, lon1, lat2, lon2):
    print(f"Calculating driving distance between ({lat1}, {lon1}) and ({lat2}, {lon2})")
    
    try:
        # Use OSRM to get the actual driving route
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok':
                # Distance is returned in meters, convert to kilometers
                distance = data['routes'][0]['distance'] / 1000
                print(f"Driving distance: {distance} km")
                return round(distance, 2)
            else:
                print(f"OSRM error: {data['code']}")
                return None
        else:
            print(f"OSRM request failed with status: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error calculating driving distance: {str(e)}")
        return None

def get_coordinates(city):
    # Use Nominatim API to get coordinates
    url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json"
    headers = {'User-Agent': 'CarPool/1.0'}
    try:
        print(f"Fetching coordinates for: {city}")
        response = requests.get(url, headers=headers)
        print(f"API Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"API Response data: {data}")
            
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                print(f"Found coordinates: {lat}, {lon}")
                return lat, lon
            else:
                print(f"No coordinates found for: {city}")
        else:
            print(f"API request failed with status: {response.status_code}")
            
    except Exception as e:
        print(f"Error getting coordinates for {city}: {str(e)}")
    return None

def maps(request):
    # Get source and destination from URL parameters
    source = request.GET.get('source', '').strip("'")  # Remove any single quotes
    destination = request.GET.get('destination', '').strip("'")  # Remove any single quotes
    
    if not source or not destination:
        messages.error(request, "Source and destination are required")
        return redirect('userHome')
        
    # Store the locations in session for later use
    request.session['current_source'] = source
    request.session['current_destination'] = destination
        
    return render(request, 'maps.html', {
        'source': source,
        'destination': destination
    })

def payment(request):
    ride_id = request.GET.get('rideId')
    if not ride_id:
        messages.error(request, "No ride selected for payment")
        return redirect('userHome')
        
    try:
        # Get ride with its distance information
        ride = RidePoint.objects.select_related('ride_distance').get(id=ride_id)
        driver = User.objects.get(id=ride.driverId)
        
        # Get distance and fare from RideDistance model
        try:
            ride_distance = ride.ride_distance
            road_distance = ride_distance.distance
            base_fare = ride_distance.fare
            
            print(f"\n=== PAYMENT DETAILS ===")
            print(f"Ride ID: {ride.id}")
            print(f"From: {ride.fromCity} To: {ride.toCity}")
            print(f"Distance: {road_distance:.2f} km")
            print(f"Base Fare: {base_fare} ETH")
            
            # Calculate individual fare for carpool
            if ride.is_carpool:
                individual_fare = float(base_fare) / 2
                print(f"Individual Fare (Carpool): {individual_fare} ETH")
            else:
                individual_fare = float(base_fare)
                print(f"Fare (Single): {individual_fare} ETH")
            
            # Get payment status for current user
            user_id = request.session.get('user_id')
            user_payment = Transaction.objects.filter(
                ride=ride,
                status='completed'
            ).first()
            
            # Check if other passenger has paid (for carpool)
            other_payment = None
            if ride.is_carpool:
                other_payment = Transaction.objects.filter(
                    ride=ride,
                    status='completed'
                ).exclude(
                    id=user_payment.id if user_payment else None
                ).first()
            
            context = {
                'rideId': ride.id,
                'driverName': driver.name,
                'driverWallet': ride.payment,  # This is the driver's wallet address
                'distance': road_distance,
                'base_fare': base_fare,
                'individual_fare': individual_fare,
                'fromCity': ride.fromCity,
                'toCity': ride.toCity,
                'is_carpool': ride.is_carpool,
                'user_paid': bool(user_payment),
                'other_paid': bool(other_payment),
                'total_paid': Transaction.objects.filter(ride=ride, status='completed').count()
            }
            
            return render(request, 'payment.html', context)
            
        except RideDistance.DoesNotExist:
            print("ERROR: No distance information available for this ride")
            messages.error(request, "Cannot process payment: Distance information not available")
            return redirect('userHome')
            
    except RidePoint.DoesNotExist:
        messages.error(request, "Invalid ride information")
        return redirect('userHome')
    except User.DoesNotExist:
        messages.error(request, "Driver information not found")
        return redirect('userHome')
    except Exception as e:
        print(f"Error in payment view: {str(e)}")  # Debug log
        messages.error(request, f"Error processing payment: {str(e)}")
        return redirect('userHome')

def AcceptTheRide(request):
    if request.method == "POST":
        rideId = request.POST.get("rideId", "")
        userId = request.POST.get("userId", "")
        walletAddress = request.POST.get("walletAddress", "").strip()
        
        if not walletAddress:
            messages.error(request, "Please enter your blockchain wallet address")
            return redirect("driverHome")
            
        try:
            # Update ride with driver info and wallet address
            ride = RidePoint.objects.get(id=int(rideId))
            if ride.driverId:  # Check if ride is already accepted
                messages.error(request, "This ride has already been accepted by another driver")
                return redirect("driverHome")
                
            ride.driverId = userId
            ride.status = "Accepted By Driver"
            ride.payment = walletAddress  # Store wallet address in payment field
            ride.save()
            
            messages.success(request, "Successfully Accepted")
            return redirect("acceptance", userid=userId)  # Redirect to accepted rides
        except RidePoint.DoesNotExist:
            messages.error(request, "Invalid ride ID")
            return redirect("driverHome")
        except Exception as e:
            messages.error(request, f"Error accepting ride: {str(e)}")
            return redirect("driverHome")


def stateOFCompleted(request):
    if request.method == "POST":
        rideId = request.POST.get("rideId", "").strip()
        driverId = request.session.get('driver_id')
        
        if not rideId or not driverId:
            messages.error(request, "Missing required information")
            return redirect("acceptance", userid=driverId)
            
        try:
            # Get the ride
            ride = RidePoint.objects.get(id=rideId)
            
            # Verify this is the correct driver
            if str(ride.driverId) != str(driverId):
                messages.error(request, "Unauthorized access")
                return redirect("driverHome")
                
            # Get ride distance information
            try:
                ride_distance = ride.ride_distance
                road_distance = ride_distance.distance
                
                # Update ride status
                ride.status = "Ride Completed"
                ride.save()
                
                # Create transaction for solo ride
                if not ride.is_carpool:
                    # Check if transaction already exists
                    existing_transaction = Transaction.objects.filter(
                        ride=ride,
                        driver_id=driverId,
                        source=ride.fromCity,
                        destination=ride.toCity
                    ).first()
                    
                    if not existing_transaction:
                        # For solo rides, use the full base fare
                        transaction = Transaction.objects.create(
                            ride=ride,
                            driver=User.objects.get(id=driverId),
                            source=ride.fromCity,
                            destination=ride.toCity,
                            distance=road_distance,
                            fare=float(ride.base_fare),
                            status='pending',
                            passenger_count=1,
                            is_carpool=False
                        )
                        print(f"Created transaction for solo ride {ride.id}")
                        print(f"Fare: {ride.base_fare} ETH")
                    else:
                        print(f"Transaction already exists for solo ride {ride.id}")
                
                # Handle carpool rides
                else:
                    # Get all passengers for this ride
                    passengers = JointRide.objects.filter(rideId=rideId)
                    passenger_count = passengers.count()
                    
                    # Create transaction for each passenger
                    for passenger in passengers:
                        # Check if transaction already exists
                        existing_transaction = Transaction.objects.filter(
                            ride=ride,
                            driver_id=driverId,
                            source=ride.fromCity,
                            destination=ride.toCity
                        ).first()
                        
                        if not existing_transaction:
                            # Calculate individual fare for carpool
                            individual_fare = float(ride.base_fare) / 2
                            
                            transaction = Transaction.objects.create(
                                ride=ride,
                                driver=User.objects.get(id=driverId),
                                source=ride.fromCity,
                                destination=ride.toCity,
                                distance=road_distance,
                                fare=individual_fare,
                                status='pending',
                                passenger_count=passenger_count,
                                is_carpool=True
                            )
                            print(f"Created transaction for passenger {passenger.userid}")
                            print(f"Individual fare: {individual_fare} ETH")
                        else:
                            print(f"Transaction already exists for passenger {passenger.userid}")
                
                messages.success(request, "Ride completed successfully")
                return redirect("acceptance", userid=driverId)  # Redirect back to accepted rides page
                
            except RideDistance.DoesNotExist:
                print("ERROR: No distance information available for this ride")
                messages.error(request, "Cannot complete ride: Distance information not available")
                return redirect("acceptance", userid=driverId)
                
        except RidePoint.DoesNotExist:
            messages.error(request, "Ride not found")
            return redirect("acceptance", userid=driverId)
        except Exception as e:
            print(f"Error completing ride: {str(e)}")
            messages.error(request, f"Error completing ride: {str(e)}")
            return redirect("acceptance", userid=driverId)
            
    return redirect("driverHome")

def transactions(request):
    if 'driver_id' in request.session:
        # For drivers, show transactions where they are the driver
        transactions = Transaction.objects.filter(
            driver__id=request.session['driver_id']
        ).order_by('-created_at')
    elif 'user_id' in request.session:
        # For users, show transactions where they are the passenger
        transactions = Transaction.objects.filter(
            Q(ride__userid=request.session['user_id']) |  # Direct rides
            Q(ride__id__in=JointRide.objects.filter(userid=request.session['user_id']).values_list('rideId', flat=True))  # Joined rides
        ).order_by('-created_at')
    else:
        messages.error(request, "Please login to view transactions")
        return redirect('login')
    
    # Group transactions by status
    # Show completed rides in pending transactions until payment is made
    # pending_transactions = transactions.filter(
    #     Q(status='pending') |  # Regular pending transactions
    #     Q(status='completed', transaction_hash__isnull=True)  # Completed rides waiting for payment
    # )
    
    # Show only paid transactions in completed
    completed_transactions = transactions.filter(
        status='completed',
        transaction_hash__isnull=False  # Only show transactions with payment hash
    )
    
    return render(request, 'driver/transactions.html', {
        'transactions': transactions,
        'pending_transactions': [],  # Empty list since we're not showing pending transactions
        'completed_transactions': completed_transactions
    })

@login_required(login_url="login")
def getJoinPool(request):
    try:
        # Get search parameters
        source = request.GET.get('source', '')
        destination = request.GET.get('destination', '')
        date = request.GET.get('date', '')

        # Get rides that user hasn't created or joined
        rides = RidePoint.objects.filter(
            ~Q(userid=request.session['user_id']) &  # Not created by user
            ~Q(id__in=JointRide.objects.filter(userid=request.session['user_id']).values_list('rideId', flat=True)) &  # Not joined by user
            ~Q(status="Ride Completed") &  # Not completed
            Q(passenger_count__lt=2)  # Less than 2 passengers
        )

        # Apply filters if provided
        if source:
            rides = rides.filter(fromCity__icontains=source)
        if destination:
            rides = rides.filter(toCity__icontains=destination)
        if date:
            rides = rides.filter(datePoint__icontains=date)

        # Convert to list for sorting
        rides_list = list(rides)
        
        # Sort rides by date and time
        def get_sort_key(ride):
            try:
                # Parse the date and time from datePoint
                date_str = ride.datePoint
                if isinstance(date_str, datetime.datetime):
                    return date_str
                return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except Exception as e:
                print(f"Error getting sort key for ride {ride.id}: {str(e)}")
                return datetime.datetime.min

        rides_list.sort(key=get_sort_key)

        # Convert to dictionary format for JSON response
        data = []
        for ride in rides_list:
            ride_data = {
                "id": ride.id,
                "fromCity": ride.fromCity,
                "toCity": ride.toCity,
                "datePoint": ride.datePoint,
                "journey_time": ride.journey_time,
                "contactPoint": ride.contactPoint,
                "status": ride.status,
                "passenger_count": ride.passenger_count
            }
            data.append(ride_data)

        return JsonResponse({"data": data})

    except Exception as e:
        print(f"Error in getJoinPool: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@login_required(login_url="login")
def myPool(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'User not logged in'}, status=401)
    # Get all rides the user has joined, ordered by joined_at timestamp
    joined_rides = JointRide.objects.filter(userid=user_id).order_by('-joined_at')
    ride_ids = joined_rides.values_list('rideId', flat=True)
    rides = RidePoint.objects.filter(id__in=ride_ids)
    rides_list = list(rides.values('id', 'fromCity', 'toCity', 'datePoint', 'contactPoint', 'status', 'passenger_count', 'is_carpool', 'current_fare'))
    return JsonResponse({'data': rides_list})

def joinPool(request):
    # Check if user is logged in
    if not request.session.get('user_id'):
        messages.error(request, "Please login to view available rides")
        return redirect('login')
        
    if request.method == "GET":
        # If it's an AJAX request, return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                source = request.GET.get("source", "")
                destination = request.GET.get("destination", "")
                date = request.GET.get("date", "")
                user_id = str(request.session['user_id'])
                
                # Get all rides that:
                # 1. Are not created by this user
                # 2. Are not already joined by this user
                # 3. Are not completed
                # 4. Have less than 2 passengers
                rides = RidePoint.objects.exclude(
                    Q(userid=user_id) |  # Exclude rides created by the user
                    Q(id__in=JointRide.objects.filter(userid=user_id).values_list('rideId', flat=True)) |  # Exclude rides already joined
                    Q(status="Ride Completed")  # Exclude completed rides
                ).filter(
                    passenger_count__lt=2  # Only show rides with less than 2 passengers
                )
                
                # Apply source and destination filters if provided
                if source:
                    rides = rides.filter(fromCity__icontains=source)
                if destination:
                    rides = rides.filter(toCity__icontains=destination)
                if date:
                    rides = rides.filter(datePoint__icontains=date)
                    
                # Order by distance
                rides = rides.select_related('ride_distance').order_by('ride_distance__distance')
                
                rides_list = list(rides.values(
                    'id', 'fromCity', 'toCity', 'datePoint', 'journey_time',
                    'contactPoint', 'status', 'passenger_count', 'is_carpool',
                    'base_fare', 'current_fare', 'ride_distance__distance'
                ))
                
                # Rename the distance field
                for ride in rides_list:
                    ride['distance'] = ride.pop('ride_distance__distance', None)
                
                return JsonResponse({"data": rides_list})
            except Exception as e:
                print(f"Error in joinPool: {str(e)}")  # Debug log
                return JsonResponse({"error": str(e)}, status=500)
        return render(request, "joinPool.html")
    elif request.method == "POST":
        poolId = request.POST.get("poolId")
        userId = request.session.get('user_id')
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        
        if not all([poolId, userId, email, phone]):
            messages.error(request, "Missing required information")
            return redirect("joinPool")
            
        try:
            ride = RidePoint.objects.get(id=poolId)
            if ride.status == "Ride Completed":
                messages.error(request, "This ride is no longer available")
                return redirect("joinPool")
            if JointRide.objects.filter(rideId=poolId, userid=userId).exists():
                messages.error(request, "You have already joined this ride")
                return redirect("joinPool")
            current_passengers = JointRide.objects.filter(rideId=poolId).count()
            if current_passengers >= 2:
                messages.error(request, "This ride is full")
                return redirect("joinPool")
                
            # Calculate fare based on number of passengers
            if current_passengers == 0:
                ride.base_fare = float(ride.payment)
                ride.current_fare = float(ride.payment)
                ride.is_carpool = True
                ride.passenger_count = 1
                ride.save()
                payment_amount = float(ride.payment)
            else:
                payment_amount = float(ride.base_fare) / 2
                ride.current_fare = payment_amount
                ride.passenger_count = 2  # Update passenger count to 2
                ride.save()
                first_passenger = JointRide.objects.get(rideId=poolId)
                first_passenger.payment_amount = payment_amount
                first_passenger.save()
                
            # Create the joint ride
            JointRide.objects.create(
                userid=userId,
                rideId=poolId,
                email=email,
                phone=phone,
                payment_amount=payment_amount
            )
            
            # Update passenger count in RidePoint
            ride.refresh_from_db()  # Refresh to get latest data
            ride.passenger_count = 2  # Set to 2 since we have creator + 1 joiner
            ride.save()
            
            messages.success(request, "Successfully joined the pool!")
        except RidePoint.DoesNotExist:
            messages.error(request, "Invalid ride")
        except Exception as e:
            messages.error(request, f"Error joining pool: {str(e)}")
        return redirect("joinPool")


def stateOF(request):
    if not request.session.get('driver_id') or request.session.get('driver_type') != 'driver':
        messages.error(request, "Please login as a driver")
        return redirect('login')
        
    if request.method == "POST":
        rideId = request.POST.get("rideId", 0).strip()
        driverId = request.POST.get("driverId", "").strip()
        walletAddress = request.POST.get("walletAddress", "").strip()
        
        if not walletAddress:
            messages.error(request, "Please enter your blockchain wallet address")
            return redirect("driverHome")
            
        try:
            # Update ride with driver info and wallet address
            ride = RidePoint.objects.get(id=int(rideId))
            if ride.driverId:  # Check if ride is already accepted
                messages.error(request, "This ride has already been accepted by another driver")
                return redirect("driverHome")
                
            ride.driverId = driverId
            ride.status = "Accepted By Driver"
            ride.payment = walletAddress  # Store wallet address in payment field
            ride.save()
            
            messages.success(request, "Successfully Accepted")
            return redirect("acceptance", userid=driverId)  # Redirect to accepted rides
        except RidePoint.DoesNotExist:
            messages.error(request, "Invalid ride ID")
            return redirect("driverHome")
        except Exception as e:
            messages.error(request, f"Error accepting ride: {str(e)}")
            return redirect("driverHome")
            
    return redirect("driverHome")


def rejectRide(request):
    if request.method == "POST":
        try:
            rideId = request.POST.get("rideId", "").strip()
            driverId = request.POST.get("driverId", "").strip()
            
            if not rideId or not driverId:
                messages.error(request, "Missing required information")
                return redirect("driverHome")
                
            # Get the ride
            ride = RidePoint.objects.get(id=int(rideId))
            
            # Check if ride is already accepted by any driver
            if ride.driverId:
                messages.error(request, "This ride has already been accepted by another driver")
                return redirect("driverHome")
                
            # Check if this driver has already rejected this ride
            if RejectedRide.objects.filter(rideId=rideId, driverId=driverId).exists():
                messages.error(request, "You have already rejected this ride")
                return redirect("driverHome")
                
            # Create rejection record
            RejectedRide.objects.create(
                rideId=rideId,
                driverId=driverId
            )
            
            messages.success(request, "Ride rejected successfully")
            
        except RidePoint.DoesNotExist:
            messages.error(request, "Invalid ride ID")
        except ValueError:
            messages.error(request, "Invalid ride ID format")
        except Exception as e:
            messages.error(request, f"Error rejecting ride: {str(e)}")
            
    return redirect("driverHome")


def acceptance(request, userid=0):
    if not request.session.get('driver_id') or request.session.get('driver_type') != 'driver':
        messages.error(request, "Please login as a driver")
        return redirect('login')
    if str(request.session['driver_id']) != str(userid):
        messages.error(request, "Unauthorized access")
        return redirect('driverHome')
        
    print(f"\n=== FETCHING ACCEPTED RIDES ===")
    print(f"Driver ID: {userid}")
    
    try:
        # Get rides with their distance information, ordered by newest first
        rides = RidePoint.objects.filter(
            Q(driverId=userid)
            & (Q(status="Accepted By Driver") | Q(status="Ride Completed"))
        ).select_related('ride_distance').order_by('-applyOn')  # Order by newest first
        
        rideDate = []
        for ride in rides:
            # Get distance information
            try:
                distance = ride.ride_distance.distance
                fare = ride.ride_distance.fare
                print(f"Ride {ride.id}: Distance={distance}km, Fare={fare}ETH")
            except RideDistance.DoesNotExist:
                # If no distance record exists, try to calculate it
                try:
                    source_coords = get_coordinates(ride.fromCity)
                    dest_coords = get_coordinates(ride.toCity)
                    
                    if source_coords and dest_coords:
                        distance = calculate_distance(
                            source_coords[0], source_coords[1],
                            dest_coords[0], dest_coords[1]
                        )
                        fare = round(float(distance) * 0.000055, 6)
                        
                        # Create the distance record
                        RideDistance.objects.create(
                            ride=ride,
                            distance=distance,
                            fare=fare
                        )
                        print(f"Created new distance record: {distance}km, {fare}ETH")
                    else:
                        distance = None
                        fare = None
                        print(f"Could not get coordinates for ride {ride.id}")
                except Exception as e:
                    print(f"Error calculating distance for ride {ride.id}: {str(e)}")
                    distance = None
                    fare = None
            
            ride_data = {
                "id": ride.id,
                "fromCity": ride.fromCity,
                "toCity": ride.toCity,
                "datePoint": ride.datePoint,
                "contactPoint": ride.contactPoint,
                "status": ride.status,
                "userid": ride.userid,
                "driverId": ride.driverId,
                "applyOn": ride.applyOn,
                "payment": ride.payment,
                "distance": distance,
                "fare": fare,
                "is_carpool": ride.is_carpool
            }
            rideDate.append(ride_data)
        
        # Get user details
        users_ids = [ride["userid"] for ride in rideDate]
        users = User.objects.filter(id__in=users_ids).values(
            "id", "name", "email", "typeView"
        )
        usermap = {str(user["id"]): user for user in users}

        for ride in rideDate:
            ride["userDetails"] = usermap.get(ride["userid"], {})

        completed = list()
        accepted = list()
        for ride2 in rideDate:
            if ride2["status"] == "Accepted By Driver":
                accepted.append(ride2)
            elif ride2["status"] == "Ride Completed":
                completed.append(ride2)

        print(f"Accepted rides: {len(accepted)}, Completed rides: {len(completed)}")
        print("==============================\n")

        return render(
            request,
            "driver/accepted.html",
            context={"accepted": accepted, "completed": completed},
        )
    except Exception as e:
        print(f"Error in acceptance view: {str(e)}")
        messages.error(request, f"Error loading rides: {str(e)}")
        return redirect("driverHome")


def driverHome(request):
    if not request.session.get('driver_id') or request.session.get('driver_type') != 'driver':
        messages.error(request, "Please login as a driver")
        return redirect('login')
        
    # Get rides that haven't been accepted and haven't been rejected by this driver
    data = RidePoint.objects.filter(
        Q(driverId="") & 
        ~Q(userid="") &
        ~Q(id__in=RejectedRide.objects.filter(driverId=str(request.session['driver_id'])).values_list('rideId', flat=True))
    ).order_by('-applyOn')

    # Convert to list to modify the data
    rides_list = []
    for ride in data:
        # Get all joiners for this ride
        joiners = JointRide.objects.filter(rideId=ride.id)
        total_passengers = 1 + joiners.count()  # Creator + joiners

        ride_data = {
            "id": ride.id,
            "fromCity": ride.fromCity,
            "toCity": ride.toCity,
            "datePoint": ride.datePoint,
            "contactPoint": ride.contactPoint,
            "status": ride.status,
            "userid": ride.userid,
            "driverId": ride.driverId,
            "applyOn": ride.applyOn,
            "is_carpool": ride.is_carpool,
            "passenger_count": total_passengers,
            "passengers": []
        }

        # Get creator details
        creator = User.objects.filter(id=ride.userid).first()
        if creator:
            passenger_data = {
                "name": creator.name,
                "phone": ride.phone_number,
                "email": creator.email,
                "is_creator": True
            }
            ride_data["passengers"].append(passenger_data)

        # Get joiner details
        for joiner in joiners:
            joiner_user = User.objects.filter(id=joiner.userid).first()
            if joiner_user:
                ride_data["passengers"].append({
                    "name": joiner_user.name,
                    "phone": joiner.phone,
                    "email": joiner.email,
                    "is_creator": False
                })

        rides_list.append(ride_data)

    return render(request, "driver/home.html", context={"data": rides_list})


def profileDetails(request):
    userId = request.GET.get("userid", 0)
    data = User.objects.filter(id=int(userId)).values(
        "name", 
        "email", 
        "typeView", 
        "gender",
        "emergency_contact_name",
        "emergency_contact_email",
        "emergency_contact_mobile"
    )
    return JsonResponse({"profile": list(data)})


def profile(request):
    if not request.session.get('user_id') or request.session.get('user_type') != 'user':
        messages.error(request, "Please login as a user")
        return redirect('login')
    return render(request, "user/profile.html")


def getRequestFromUsers(request):
    try:
        userid = request.GET.get("userid", "")
        print(f"\n=== FETCHING RIDES FOR USER {userid} ===")
        
        if not userid:
            print("ERROR: No user ID provided")
            return JsonResponse({"error": "User ID is required"}, status=400)
            
        try:
            # Get direct rides (created by the user)
            print("Fetching direct rides...")
            user_rides = list(RidePoint.objects.filter(userid=str(userid))
                .select_related('ride_distance')
                .values(
                    "fromCity",
                    "toCity",
                    "datePoint",
                    "journey_time",
                    "phone_number",
                    "contactPoint",
                    "status",
                    "driverId",
                    "applyOn",
                    "id",
                    "ride_distance__distance",
                    "ride_distance__fare",
                    "passenger_count",
                    "is_carpool",
                    "base_fare",
                    "current_fare"
                ))
            print(f"Found {len(user_rides)} direct rides")
            
            # Process direct rides
            for ride in user_rides:
                try:
                    # Get the actual ride object to access ride_distance
                    ride_obj = RidePoint.objects.select_related('ride_distance').get(id=ride['id'])
                    if hasattr(ride_obj, 'ride_distance'):
                        ride['distance'] = ride_obj.ride_distance.distance
                        ride['fare'] = ride_obj.ride_distance.fare
                    else:
                        # If no ride_distance exists, calculate it
                        source_coords = get_coordinates(ride['fromCity'])
                        dest_coords = get_coordinates(ride['toCity'])
                        
                        if source_coords and dest_coords:
                            distance = calculate_distance(
                                source_coords[0], source_coords[1],
                                dest_coords[0], dest_coords[1]
                            )
                            fare = round(float(distance) * 0.000055, 6)
                            
                            # Create the distance record
                            RideDistance.objects.create(
                                ride=ride_obj,
                                distance=distance,
                                fare=fare
                            )
                            ride['distance'] = distance
                            ride['fare'] = fare
                        else:
                            ride['distance'] = None
                            ride['fare'] = None
                    
                    # Count total passengers (creator + joiners)
                    joiners = JointRide.objects.filter(rideId=ride['id']).count()
                    total_passengers = 1 + joiners  # Creator + joiners
                    
                    # Update the passenger count in the ride object
                    ride_obj.passenger_count = total_passengers
                    ride_obj.save()
                    
                    # Update the passenger count in the response
                    ride['passenger_count'] = total_passengers
                    
                    if ride.get('applyOn'):
                        ride['applyOn'] = ride['applyOn'].strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    print(f"Error processing direct ride {ride.get('id')}: {str(e)}")
                    continue
                    
            # Get joint rides
            print("Fetching joint rides...")
            joint_rides = JointRide.objects.filter(userid=str(userid)).values(
                "id", "userid", "rideId", "joined_at"
            )
            print(f"Found {len(joint_rides)} joint rides")
            
            if joint_rides.exists():
                try:
                    # Create mapping of ride IDs to joined_at timestamps
                    ride_ids = [int(d["rideId"]) for d in joint_rides]
                    joined_at_map = {str(d["rideId"]): d["joined_at"] for d in joint_rides}
                    
                    # Get associated rides
                    print("Fetching associated rides...")
                    associated_rides = RidePoint.objects.filter(id__in=ride_ids).select_related('ride_distance').values(
                        "fromCity",
                        "toCity",
                        "datePoint",
                        "journey_time",
                        "phone_number",
                        "contactPoint",
                        "status",
                        "driverId",
                        "applyOn",
                        "id",
                        "ride_distance__distance",
                        "ride_distance__fare",
                        "passenger_count",
                        "is_carpool",
                        "base_fare",
                        "current_fare"
                    )
                    
                    # Process associated rides
                    associated_rides_list = list(associated_rides)
                    for ride in associated_rides_list:
                        try:
                            # Get the actual ride object to access ride_distance
                            ride_obj = RidePoint.objects.select_related('ride_distance').get(id=ride['id'])
                            if hasattr(ride_obj, 'ride_distance'):
                                ride['distance'] = ride_obj.ride_distance.distance
                                ride['fare'] = ride_obj.ride_distance.fare
                            else:
                                # If no ride_distance exists, calculate it
                                source_coords = get_coordinates(ride['fromCity'])
                                dest_coords = get_coordinates(ride['toCity'])
                                
                                if source_coords and dest_coords:
                                    distance = calculate_distance(
                                        source_coords[0], source_coords[1],
                                        dest_coords[0], dest_coords[1]
                                    )
                                    fare = round(float(distance) * 0.000055, 6)
                                    
                                    # Create the distance record
                                    RideDistance.objects.create(
                                        ride=ride_obj,
                                        distance=distance,
                                        fare=fare
                                    )
                                    ride['distance'] = distance
                                    ride['fare'] = fare
                                else:
                                    ride['distance'] = None
                                    ride['fare'] = None
                            
                            # Count total passengers (creator + joiners)
                            joiners = JointRide.objects.filter(rideId=ride['id']).count()
                            total_passengers = 1 + joiners  # Creator + joiners
                            
                            # Update the passenger count in the ride object
                            ride_obj.passenger_count = total_passengers
                            ride_obj.save()
                            
                            # Update the passenger count in the response
                            ride['passenger_count'] = total_passengers
                            
                            ride['joined_at'] = joined_at_map[str(ride['id'])]
                            if ride.get('applyOn'):
                                ride['applyOn'] = ride['applyOn'].strftime('%Y-%m-%d %H:%M:%S')
                            if ride.get('joined_at'):
                                ride['joined_at'] = ride['joined_at'].strftime('%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            print(f"Error processing associated ride {ride.get('id')}: {str(e)}")
                            continue
                            
                    user_rides.extend(associated_rides_list)
                    print(f"Added {len(associated_rides_list)} joint rides")
                except Exception as e:
                    print(f"Error processing joint rides: {str(e)}")
            
            # Sort rides by most recent activity
            print("Sorting rides...")
            def get_sort_key(ride):
                try:
                    # Get the timestamp string
                    joined_at = ride.get('joined_at')
                    apply_on = ride.get('applyOn')
                    
                    # Convert string timestamps to datetime objects for comparison
                    if joined_at:
                        return datetime.strptime(joined_at, '%Y-%m-%d %H:%M:%S')
                    elif apply_on:
                        return datetime.strptime(apply_on, '%Y-%m-%d %H:%M:%S')
                    return datetime.min  # Default to earliest possible date
                except Exception as e:
                    print(f"Error getting sort key for ride {ride.get('id')}: {str(e)}")
                    return datetime.min
                    
            user_rides.sort(key=get_sort_key, reverse=True)
            
            print(f"Total rides after processing: {len(user_rides)}")
            print("==============================\n")
            
            return JsonResponse({"data": user_rides})
            
        except Exception as e:
            print(f"Error in main processing: {str(e)}")
            raise
            
    except Exception as e:
        print(f"\n=== ERROR IN getRequestFromUsers ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("==============================\n")
        return JsonResponse({"error": str(e)}, status=500)

def addPool(request):
    # Check if user is logged in via session
    if not request.session.get('user_id'):
        messages.error(request, "Please login to add a pool")
        return redirect('login')
        
    if request.method == "POST":
        fromCity = request.POST.get("formPoint", "").strip()
        toCity = request.POST.get("toPoint", "").strip()
        datePoint = request.POST.get("datePoint", "").strip()
        journeyTime = request.POST.get("journeyTime", "").strip()
        phoneNumber = request.POST.get("phoneNumber", "").strip()
        contactPoint = request.POST.get("contactPoint", "").strip()
        userId = str(request.session.get("user_id"))
        output = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n=== CREATING NEW POOL ===")
        print(f"User ID: {userId}")
        print(f"From: {fromCity} To: {toCity}")
        print(f"Date: {datePoint} Time: {journeyTime}")
        print(f"Phone: +91{phoneNumber}")
        
        if not fromCity or not toCity:
            messages.error(request, "Pickup and destination locations are required")
            return redirect('userHome')
            
        if not phoneNumber or len(phoneNumber) != 10:
            messages.error(request, "Please enter a valid 10-digit phone number")
            return redirect('userHome')
            
        # Get road distance from session
        distance = request.session.get('current_ride_distance')
        print(f"Road distance from session: {distance}")
        
        if not distance or float(distance) <= 0:
            print("ERROR: Invalid or missing distance, redirecting to maps")
            return redirect(f'/maps?source={fromCity}&destination={toCity}')
            
        try:
            distance = float(distance)
            if distance <= 0:
                raise ValueError("Distance must be greater than 0")
                
            print(f"Creating pool with road distance: {distance} km")
            # Calculate fare based on distance (0.000055 ETH per km)
            fare = round(distance * 0.000055, 6)
            print(f"Calculated fare: {fare} ETH")
            
            # Create the pool with initial passenger count of 1
            pool = RidePoint.objects.create(
                fromCity=fromCity,
                toCity=toCity,
                datePoint=datePoint,
                journey_time=journeyTime,
                contactPoint=contactPoint,
                phone_number=f"+91{phoneNumber}",
                status="Waiting for driver to accept",
                userid=userId,
                driverId="",
                applyOn=output,
                payment=str(fare),
                passenger_count=1,  # Set initial passenger count to 1 (the creator)
                is_carpool=True,    # Mark as carpool since it's created for sharing
                base_fare=fare,     # Set base fare
                current_fare=fare   # Set current fare
            )
            
            # Create the ride distance record
            ride_distance = RideDistance.objects.create(
                ride=pool,
                distance=distance,
                fare=fare
            )
            
            # Double-check passenger count is set correctly
            pool.refresh_from_db()
            if pool.passenger_count != 1:
                pool.passenger_count = 1
                pool.save()
            
            print(f"Pool created successfully with ID: {pool.id}")
            print(f"Passenger count: {pool.passenger_count}")
            print(f"Stored distance: {ride_distance.distance} km")
            print(f"Stored fare: {ride_distance.fare} ETH")
            print("==============================\n")
            
            # Clear the distance from session after successful creation
            if 'current_ride_distance' in request.session:
                del request.session['current_ride_distance']
            messages.success(request, "Pool added successfully!")
            return redirect('userHome')
        except ValueError as e:
            print(f"Error: Invalid distance value - {str(e)}")
            messages.error(request, "Invalid distance value. Please try again.")
            return redirect('userHome')
        except Exception as e:
            print(f"Error creating pool: {str(e)}")
            messages.error(request, f"Error adding pool: {str(e)}")
            return redirect('userHome')
            
    return render(request, "user/add_pool.html")


def userHome(request):
    if not request.session.get('user_id') or request.session.get('user_type') != 'user':
        messages.error(request, "Please login as a user")
        return redirect('login')
    return render(request, "user/home.html")


def index(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        # Find user by email and password
        data = User.objects.filter(email=email, password=password)

        if data.exists():
            user = data.first()
            
            # Store user info in session based on type
            if user.typeView == "driver":
                request.session['driver_id'] = str(user.id)
                request.session['driver_type'] = user.typeView
            else:
                request.session['user_id'] = str(user.id)
                request.session['user_type'] = user.typeView
                
            request.session.set_expiry(86400)  # 24 hours

            messages.success(request, f"Successfully logged in as {user.typeView}")

            # Redirect based on user type
            if user.typeView == "driver":
                return redirect("driverHome")
            elif user.typeView == "user":
                return redirect("userHome")

        messages.error(request, "Invalid credentials")
        return redirect("login")

    return render(request, "login.html")


def signup(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        if User.objects.filter(email=email).exists():
            messages.info(request, "Try with another email !!")
            return redirect("signup")

        User.objects.create(name=name, email=email, password=password, typeView="user")
        messages.info(request, "Success")
        return redirect("login")

    return render(request, "signup.html")


def dregister(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        if User.objects.filter(email=email).exists():
            messages.info(request, "Try with another email !!")
            return redirect("dregister")

        User.objects.create(
            name=name, email=email, password=password, typeView="driver"
        )
        messages.info(request, "Success")
        return redirect("login")

    return render(request, "driverRegister.html")

def logout(request):
    request.session.flush()
    messages.success(request, "Successfully logged out")
    return redirect('login')

def updateTransaction(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            ride_id = data.get('rideId')
            tx_hash = data.get('transactionHash')
            user_id = request.session.get('user_id')
            
            print(f"\n=== UPDATING TRANSACTION ===")
            print(f"Ride ID: {ride_id}")
            print(f"Transaction Hash: {tx_hash}")
            print(f"User ID: {user_id}")
            
            if not ride_id or not tx_hash or not user_id:
                print("ERROR: Missing required fields")
                return JsonResponse({'success': False, 'error': 'Missing required fields'})
                
            # Get the ride and check if it's a carpool
            ride = RidePoint.objects.get(id=ride_id)
            print(f"Ride Type: {'Carpool' if ride.is_carpool else 'Single'}")
            print(f"Passenger Count: {ride.passenger_count}")
            
            # Check if user has already paid
            existing_user_tx = Transaction.objects.filter(
                ride_id=ride_id,
                status='completed'
            ).first()
            
            if existing_user_tx:
                print(f"User has already paid for this ride")
                return JsonResponse({
                    'success': True,
                    'message': 'Payment already recorded',
                    'transaction_id': existing_user_tx.id,
                    'ride_id': ride_id
                })
            
            # Create new transaction for this user's payment
            try:
                # Get the ride distance
                ride_distance = ride.ride_distance
                road_distance = ride_distance.distance
                
                # Calculate individual fare
                if ride.is_carpool:
                    individual_fare = float(ride.base_fare) / 2
                else:
                    individual_fare = float(ride.base_fare)
                
                # Create new transaction
                transaction = Transaction.objects.create(
                    ride=ride,
                    driver=User.objects.get(id=ride.driverId),
                    source=ride.fromCity,
                    destination=ride.toCity,
                    distance=road_distance,
                    fare=individual_fare,
                    status='completed',
                    transaction_hash=tx_hash,
                    passenger_count=ride.passenger_count,
                    is_carpool=ride.is_carpool
                )
                print(f"Created new transaction {transaction.id} for user payment")
                
                # Check if all payments are completed
                all_transactions = Transaction.objects.filter(ride_id=ride_id)
                completed_transactions = all_transactions.filter(status='completed')
                
                if completed_transactions.count() == ride.passenger_count:
                    ride.status = "Payment Completed"
                    ride.save()
                    print("All passengers have paid. Marking ride as Payment Completed")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Payment recorded successfully',
                    'transaction_id': transaction.id,
                    'ride_id': ride_id,
                    'is_carpool': ride.is_carpool,
                    'total_passengers': ride.passenger_count,
                    'completed_payments': completed_transactions.count()
                })
                
            except Exception as e:
                print(f"ERROR creating transaction: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Payment received but failed to record transaction. Please contact support with transaction hash.'
                })
            
        except RidePoint.DoesNotExist:
            print(f"ERROR: Ride not found for ID {ride_id}")
            return JsonResponse({'success': False, 'error': 'Ride not found'})
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
        finally:
            print("==============================\n")
            
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def payment_success(request):
    try:
        hash = request.GET.get('hash', '')
        distance = request.GET.get('distance', '')
        amount = request.GET.get('amount', '')
        
        if not all([hash, distance, amount]):
            messages.error(request, "Missing transaction details")
            return redirect('userHome')
        
        context = {
            'hash': hash,
            'distance': distance,
            'amount': amount
        }
        
        return render(request, 'payment_success.html', context)
    except Exception as e:
        messages.error(request, f"Error displaying payment success: {str(e)}")
        return redirect('userHome')

@require_http_methods(["POST"])
def update_distance(request):
    try:
        data = json.loads(request.body)
        distance = data.get('distance')
        
        print("\n=== UPDATING DISTANCE ===")
        print(f"Received distance: {distance}")
        
        if distance is None:
            print("ERROR: No distance provided")
            return JsonResponse({'success': False, 'error': 'No distance provided'})
            
        try:
            distance = float(distance)
            if distance <= 0:
                print("ERROR: Distance must be greater than 0")
                return JsonResponse({'success': False, 'error': 'Distance must be greater than 0'})
                
            # Store the road distance in session
            request.session['current_ride_distance'] = distance
            print(f"Stored road distance in session: {distance} km")
            
            # Store the distance in DistanceCalculation model
            distance_calc = DistanceCalculation.objects.create(
                distance=distance,
                calculated_at=datetime.now()
            )
            print(f"Stored road distance in database: {distance_calc.distance} km")
            print("==============================\n")
            
            return JsonResponse({'success': True, 'distance': distance})
        except ValueError:
            print("ERROR: Invalid distance value")
            return JsonResponse({'success': False, 'error': 'Invalid distance value'})
            
    except Exception as e:
        print(f"Error updating distance: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

def deletePool(request, pool_id):
    if not request.session.get('user_id'):
        messages.error(request, "Please login to delete a pool")
        return redirect('login')
        
    try:
        pool = RidePoint.objects.get(id=pool_id)
        if str(pool.userid) != str(request.session['user_id']):
            messages.error(request, "You do not have permission to delete this pool")
            return redirect('userHome')
            
        # Only allow deletion if the pool is not completed or accepted
        if pool.status in ["Ride Completed", "Accepted By Driver"]:
            messages.error(request, "Cannot delete a completed or accepted ride")
            return redirect('userHome')
            
        # Delete any associated joint rides first
        JointRide.objects.filter(rideId=pool_id).delete()
        
        # Delete the pool
        pool.delete()
        messages.success(request, "Pool deleted successfully")
        
        # If it's an AJAX request, return JSON response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Pool deleted successfully'})
            
    except RidePoint.DoesNotExist:
        messages.error(request, "Pool not found")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Pool not found'}, status=404)
    except Exception as e:
        print(f"Error deleting pool: {str(e)}")  # Add logging
        messages.error(request, f"Error deleting pool: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
        
    return redirect('userHome')

@require_http_methods(["GET"])
def get_transactions(request):
    try:
        # Get current user ID from session
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({
                'success': False,
                'error': 'User not logged in'
            }, status=401)

        # Get filter parameters
        min_eth = request.GET.get('min_eth')
        max_eth = request.GET.get('max_eth')
        min_distance = request.GET.get('min_distance')
        max_distance = request.GET.get('max_distance')
        date_range = request.GET.get('date_range')
        sort_by = request.GET.get('sort_by')

        # Start with base queryset - filter by user's rides
        transactions = Transaction.objects.filter(ride__userid=str(user_id))

        # Apply filters
        if min_eth:
            transactions = transactions.filter(fare__gte=float(min_eth))
        if max_eth:
            transactions = transactions.filter(fare__lte=float(max_eth))
        if min_distance:
            transactions = transactions.filter(distance__gte=float(min_distance))
        if max_distance:
            transactions = transactions.filter(distance__lte=float(max_distance))
        if date_range:
            start_date, end_date = date_range.split(' to ')
            transactions = transactions.filter(
                created_at__date__gte=datetime.strptime(start_date, '%Y-%m-%d').date(),
                created_at__date__lte=datetime.strptime(end_date, '%Y-%m-%d').date()
            )

        # Apply sorting
        if sort_by:
            sort_mapping = {
                'eth_asc': 'fare',
                'eth_desc': '-fare',
                'distance_asc': 'distance',
                'distance_desc': '-distance',
                'date_desc': '-created_at',
                'date_asc': 'created_at'
            }
            transactions = transactions.order_by(sort_mapping.get(sort_by, '-created_at'))
        else:
            transactions = transactions.order_by('-created_at')

        # Convert to list of dictionaries
        transactions_list = list(transactions.values(
            'transaction_hash',
            'fare',
            'distance',
            'created_at',
            'status'
        ))

        return JsonResponse({
            'success': True,
            'transactions': transactions_list
        })

    except Exception as e:
        print(f"Error in get_transactions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@require_http_methods(["POST"])
def clear_transactions(request):
    try:
        # Delete all transactions
        Transaction.objects.all().delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Transaction history cleared successfully'
        })
    except Exception as e:
        print(f"Error in clear_transactions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

def transaction_history(request):
    if not request.session.get('user_id') or request.session.get('user_type') != 'user':
        messages.error(request, "Please login as a user")
        return redirect('login')
        
    return render(request, 'transaction_history.html')

@require_http_methods(["POST"])
def update_gender(request):
    try:
        print("\n=== UPDATING GENDER ===")
        print(f"Request body: {request.body}")
        print(f"Request content type: {request.content_type}")
        
        data = json.loads(request.body)
        print(f"Parsed data: {data}")
        
        user_id = data.get('userId')
        gender = data.get('gender')
        emergency_name = data.get('emergencyName')
        emergency_email = data.get('emergencyEmail')
        emergency_mobile = data.get('emergencyMobile')
        
        print(f"User ID: {user_id}")
        print(f"Gender: {gender}")
        
        if not user_id:
            print("ERROR: No user ID provided")
            return JsonResponse({'success': False, 'error': 'User ID is required'})
            
        if not gender:
            print("ERROR: No gender provided")
            return JsonResponse({'success': False, 'error': 'Gender is required'})
            
        try:
            # Only allow updates for users, not drivers
            user = User.objects.get(id=int(user_id))  # Convert to integer
            print(f"Found user: {user.name}")
            
            if user.typeView != "user":
                print(f"ERROR: User is not a regular user (type: {user.typeView})")
                return JsonResponse({'success': False, 'error': 'Only users can update their gender'})
                
            # Update the gender
            user.gender = gender
            print(f"Updated gender to: {gender}")
            
            # If emergency contact details are provided (for female users)
            if gender == "Female" and emergency_name and emergency_email and emergency_mobile:
                user.emergency_contact_name = emergency_name
                user.emergency_contact_email = emergency_email
                user.emergency_contact_mobile = emergency_mobile
                print("Updated emergency contact details")
            
            user.save()
            print("Changes saved successfully")
            print("==============================\n")
            
            return JsonResponse({'success': True})
            
        except User.DoesNotExist:
            print(f"ERROR: User not found with ID {user_id}")
            return JsonResponse({'success': False, 'error': 'User not found'})
        except ValueError as ve:
            print(f"ERROR: Invalid user ID format - {str(ve)}")
            return JsonResponse({'success': False, 'error': 'Invalid user ID format'})
            
    except json.JSONDecodeError as je:
        print(f"ERROR: Invalid JSON data - {str(je)}")
        return JsonResponse({'success': False, 'error': 'Invalid request data'})
    except Exception as e:
        print(f"ERROR: Unexpected error - {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_http_methods(["POST"])
def check_wallet_balance(request):
    try:
        print("\n=== CHECKING WALLET BALANCE ===")
        data = json.loads(request.body)
        wallet_address = data.get('walletAddress')
        required_amount = data.get('amount')  # Get the required payment amount
        
        if not wallet_address:
            print("ERROR: No wallet address provided")
            return JsonResponse({'error': 'Wallet address is required'}, status=400)
            
        if not required_amount:
            print("ERROR: No amount provided")
            return JsonResponse({'error': 'Payment amount is required'}, status=400)
            
        print(f"Checking balance for address: {wallet_address}")
        print(f"Required amount: {required_amount} ETH")
            
        # Initialize Web3 with Ganache
        try:
            print("Attempting to connect to Ganache...")
            # Try connecting to Ganache with a timeout
            web3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545', request_kwargs={'timeout': 5}))
            
            # Validate address format
            if not web3.is_address(wallet_address):
                print(f"ERROR: Invalid Ethereum address format: {wallet_address}")
                return JsonResponse({'error': 'Invalid Ethereum address'}, status=400)
            
            # Check if connected to Ganache
            if not web3.is_connected():
                print("ERROR: Could not connect to Ganache")
                return JsonResponse({
                    'error': 'Could not connect to Ganache. Please check:\n1. Ganache is running\n2. Ganache is on port 7545\n3. Your computer and mobile are on the same network',
                    'is_mobile_error': True
                }, status=503)
                
            print("Successfully connected to Ganache")
                
            # Get balance with timeout
            try:
                print("Getting balance...")
                balance = web3.eth.get_balance(wallet_address)
                eth_balance = web3.from_wei(balance, 'ether')
                print(f"Current balance: {eth_balance} ETH")
                
                # Convert required amount to float for comparison
                required_eth = float(required_amount)
                print(f"Required amount: {required_eth} ETH")
                
                # Check if balance is sufficient
                if float(eth_balance) < required_eth:
                    print(f"ERROR: Insufficient balance. Required: {required_eth} ETH, Available: {eth_balance} ETH")
                    return JsonResponse({
                        'success': False,
                        'error': f'Insufficient balance. Required: {required_eth} ETH, Available: {float(eth_balance):.4f} ETH',
                        'is_insufficient_balance': True,
                        'required_amount': required_eth,
                        'available_balance': float(eth_balance)
                    })
                
                print(f"Balance sufficient. Proceeding with payment...")
                return JsonResponse({
                    'success': True,
                    'balance': str(eth_balance),
                    'formatted_balance': f"{float(eth_balance):.4f} ETH",
                    'required_amount': required_eth
                })
            except Exception as e:
                print(f"ERROR getting balance: {str(e)}")
                return JsonResponse({
                    'error': 'Error getting balance. Please try again.',
                    'is_mobile_error': True
                }, status=500)
            
        except Exception as e:
            print(f"ERROR connecting to Ganache: {str(e)}")
            # Check if it's a connection error
            if "Connection refused" in str(e):
                return JsonResponse({
                    'error': 'Could not connect to Ganache. Please check:\n1. Ganache is running\n2. Ganache is on port 7545\n3. Your computer and mobile are on the same network',
                    'is_mobile_error': True
                }, status=503)
            else:
                return JsonResponse({
                    'error': f'Error connecting to Ganache: {str(e)}',
                    'is_mobile_error': True
                }, status=500)
            
    except json.JSONDecodeError as e:
        print(f"ERROR parsing JSON: {str(e)}")
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    finally:
        print("==============================\n")
