from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib import messages
from .models import *
from datetime import datetime
from django.db.models import Q
from django.urls import reverse
import json
import requests
from math import radians, sin, cos, sqrt, atan2
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

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
            fare = ride_distance.fare
            
            print(f"\n=== PAYMENT DETAILS ===")
            print(f"Ride ID: {ride.id}")
            print(f"From: {ride.fromCity} To: {ride.toCity}")
            print(f"Distance: {road_distance:.2f} km")
            print(f"Fare: {fare} ETH")
            print("==============================\n")
            
            context = {
                'rideId': ride.id,
                'driverName': driver.name,
                'driverWallet': ride.payment,  # This is the driver's wallet address
                'distance': road_distance,
                'fare': fare,
                'fromCity': ride.fromCity,
                'toCity': ride.toCity
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
        JointRide.objects.create(
            userid=userId,
            rideId=rideId,
        )
        return redirect("joinPool")


def stateOFCompleted(request):
    if request.method == "POST":
        rideId = request.POST.get("rideId", 0)
        driverId = request.session.get('driver_id')
        if not driverId:
            messages.error(request, "Please login as a driver")
            return redirect('login')
            
        try:
            # Get ride with its distance information
            ride = RidePoint.objects.select_related('ride_distance').get(id=int(rideId))
            if ride:
                print("\n=== RIDE COMPLETION DETAILS ===")
                print(f"Ride ID: {ride.id}")
                print(f"From: {ride.fromCity} To: {ride.toCity}")
                
                # Get the distance from RideDistance model
                try:
                    ride_distance = ride.ride_distance
                    road_distance = ride_distance.distance
                    fare = ride_distance.fare
                    
                    print(f"Road Distance: {road_distance:.2f} km")
                    print(f"Calculated Fare: {fare} ETH")
                    print("==============================\n")
                    
                    # Update ride status
                    ride.status = "Ride Completed"
                    ride.save()
                    
                    # Create transaction with the stored distance and fare
                    transaction = Transaction.objects.create(
                        ride=ride,
                        driver=User.objects.get(id=driverId),
                        source=ride.fromCity,
                        destination=ride.toCity,
                        distance=road_distance,
                        fare=fare,
                        status='pending'
                    )
                    print(f"Transaction created with ID: {transaction.id}")
                    print(f"Transaction details - Distance: {transaction.distance:.2f} km, Fare: {transaction.fare} ETH")
                    
                    messages.success(request, f"Ride completed. Distance: {road_distance:.2f} km, Fare: {fare} ETH")
                except RideDistance.DoesNotExist:
                    print("ERROR: No distance information available for this ride")
                    messages.error(request, "Cannot complete ride: Distance and fare information not available")
                    return redirect("acceptance", userid=driverId)
            else:
                messages.error(request, "Ride not found")
        except Exception as e:
            print(f"Error completing ride: {str(e)}")
            messages.error(request, f"Error completing ride: {str(e)}")
            
    return redirect("acceptance", userid=driverId)

def transactions(request):
    if 'driver_id' in request.session:
        # For drivers, show transactions where they are the driver
        transactions = Transaction.objects.filter(
            driver__id=request.session['driver_id']
        ).order_by('-created_at')
    elif 'user_id' in request.session:
        # For users, show transactions where they are the passenger
        transactions = Transaction.objects.filter(
            ride__userid=request.session['user_id']
        ).order_by('-created_at')
    else:
        messages.error(request, "Please login to view transactions")
        return redirect('login')
    
    return render(request, 'driver/transactions.html', {
        'transactions': transactions
    })

def getJoinPool(request):
    search = request.GET.get("search", "")
    id = request.GET.get("id", "")
    data = RidePoint.objects.filter(
        (Q(fromCity__icontains=search) | Q(toCity__icontains=search))
        & (~Q(userid=str(id)) & ~Q(status="Ride Completed"))
    ).values(
        "id",
        "fromCity",
        "toCity",
        "datePoint",
        "contactPoint",
        "status",
        "userid",
        "driverId",
        "applyOn",
        "payment",
        "distance"
    )
    data = list(data)
    result = []

    for i in range(len(data)):
        if data[i] not in ["sizeOF"]:
            jointCount = JointRide.objects.filter(rideId=int(data[i]["id"])).values(
                "id", "userid", "rideId"
            )
            view = len(list(jointCount))
            if view < 2:
                for posi in jointCount:
                    if posi["userid"] != id and view < 2:
                        data[i]['Joined']=view
                        result.append(data[i])
                if view == 0:
                    data[i]['Joined']=view
                    result.append(data[i])
    return JsonResponse({"data": result})



def joinPool(request):
    return render(request, "user/joinpool.html")


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
        rideId = request.POST.get("rideId", 0).strip()
        driverId = request.POST.get("driverId", "").strip()
        
        # Only allow rejection if this driver hasn't already accepted
        ride = RidePoint.objects.get(id=int(rideId))
        if ride.driverId == "":
            # Mark this driver as having rejected this ride
            # This prevents the same driver from seeing this ride again
            RejectedRide.objects.create(
                rideId=rideId,
                driverId=driverId
            )
            messages.success(request, "Ride rejected successfully")
        else:
            messages.error(request, "This ride has already been accepted")
            
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
        # Get rides with their distance information
        rides = RidePoint.objects.filter(
            Q(driverId=userid)
            & (Q(status="Accepted By Driver") | Q(status="Ride Completed"))
        ).select_related('ride_distance')
        
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
                "fare": fare
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
    ).values(
        "id",
        "fromCity",
        "toCity",
        "datePoint",
        "contactPoint",
        "status",
        "userid",
        "driverId",
        "applyOn",
    )
    return render(request, "driver/home.html", context={"data": data})


def profileDetails(request):
    userId = request.GET.get("userid", 0)
    data = User.objects.filter(id=int(userId)).values("name", "email", "typeView")
    return JsonResponse({"profile": list(data)})


def profile(request):
    if not request.session.get('user_id') or request.session.get('user_type') != 'user':
        messages.error(request, "Please login as a user")
        return redirect('login')
    return render(request, "user/profile.html")


def getRequestFromUsers(request):
    userid = request.GET.get("userid", "")
    print(f"Fetching rides for user: {userid}")  # Debug log
    
    # Get direct rides with their distance information, ordered by creation date (newest first)
    user_rides = list(RidePoint.objects.filter(userid=str(userid))
        .select_related('ride_distance')
        .order_by('-applyOn')  # Order by creation date in descending order
        .values(
            "fromCity",
            "toCity",
            "datePoint",
            "contactPoint",
            "status",
            "driverId",
            "applyOn",
            "id",
            "ride_distance__distance",  # Access distance through the relationship
            "ride_distance__fare"  # Also get the fare
        ))
    print(f"Found {len(user_rides)} direct rides")  # Debug log

    # Get joint rides
    joint_rides = JointRide.objects.filter(userid=str(userid)).values("id", "userid", "rideId")
    if joint_rides.exists():
        ride_ids = [int(d["rideId"]) for d in joint_rides]
        associated_rides = RidePoint.objects.filter(id__in=ride_ids).select_related('ride_distance').order_by('-applyOn').values(
            "fromCity",
            "toCity",
            "datePoint",
            "contactPoint",
            "status",
            "driverId",
            "applyOn",
            "id",
            "ride_distance__distance",  # Access distance through the relationship
            "ride_distance__fare"  # Also get the fare
        )
        user_rides.extend(list(associated_rides))
        print(f"Added {len(associated_rides)} joint rides")  # Debug log
    
    # Rename the fields to match the expected format
    for ride in user_rides:
        ride['distance'] = ride.pop('ride_distance__distance', None)
        ride['fare'] = ride.pop('ride_distance__fare', None)
    
    print(f"Total rides: {len(user_rides)}")  # Debug log
    return JsonResponse({"data": user_rides})

def addPool(request):
    # Check if user is logged in via session
    if not request.session.get('user_id'):
        messages.error(request, "Please login to add a pool")
        return redirect('login')
        
    if request.method == "POST":
        fromCity = request.POST.get("formPoint", "").strip()
        toCity = request.POST.get("toPoint", "").strip()
        datePoint = request.POST.get("datePoint", "").strip()
        contactPoint = request.POST.get("contactPoint", "").strip()
        userId = str(request.session.get("user_id"))
        output = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n=== CREATING NEW POOL ===")
        print(f"User ID: {userId}")
        print(f"From: {fromCity} To: {toCity}")
        
        if not fromCity or not toCity:
            messages.error(request, "Pickup and destination locations are required")
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
            
            # Create the pool
            pool = RidePoint.objects.create(
                fromCity=fromCity,
                toCity=toCity,
                datePoint=datePoint,
                contactPoint=contactPoint,
                status="Waiting for driver to accept",
                userid=userId,
                driverId="",
                applyOn=output,
                payment=str(fare)
            )
            
            # Create the ride distance record
            ride_distance = RideDistance.objects.create(
                ride=pool,
                distance=distance,
                fare=fare
            )
            
            print(f"Pool created successfully with ID: {pool.id}")
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
            
            print(f"Updating transaction for ride {ride_id} with hash {tx_hash}")
            
            if not ride_id or not tx_hash:
                print("Missing required fields")
                return JsonResponse({'success': False, 'error': 'Missing required fields'})
                
            # Find the transaction for this ride
            transaction = Transaction.objects.get(ride_id=ride_id)
            print(f"Found transaction: {transaction.id}")
            
            # Update transaction details
            transaction.transaction_hash = tx_hash
            transaction.status = 'completed'
            transaction.save()
            
            # Update the ride status
            ride = RidePoint.objects.get(id=ride_id)
            ride.status = "Payment Completed"
            ride.save()
            
            print(f"Transaction and ride updated successfully: {transaction.id}")
            return JsonResponse({
                'success': True,
                'message': 'Transaction updated successfully',
                'transaction_id': transaction.id,
                'ride_id': ride_id
            })
        except Transaction.DoesNotExist:
            print(f"Transaction not found for ride {ride_id}")
            return JsonResponse({'success': False, 'error': 'Transaction not found'})
        except RidePoint.DoesNotExist:
            print(f"Ride not found for ID {ride_id}")
            return JsonResponse({'success': False, 'error': 'Ride not found'})
        except Exception as e:
            print(f"Error updating transaction: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
            
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
    if not request.session.get('user_id') or request.session.get('user_type') != 'user':
        messages.error(request, "Please login as a user")
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
            
        pool.delete()
        messages.success(request, "Pool deleted successfully")
    except RidePoint.DoesNotExist:
        messages.error(request, "Pool not found")
    except Exception as e:
        messages.error(request, f"Error deleting pool: {str(e)}")
        
    return redirect('userHome')

@require_http_methods(["GET"])
def get_transactions(request):
    try:
        # Get filter parameters
        min_eth = request.GET.get('min_eth')
        max_eth = request.GET.get('max_eth')
        min_distance = request.GET.get('min_distance')
        max_distance = request.GET.get('max_distance')
        date_range = request.GET.get('date_range')
        sort_by = request.GET.get('sort_by')

        # Start with base queryset
        transactions = Transaction.objects.all()

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
