from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib import messages
from .models import *
from datetime import datetime
from django.db.models import Q
from django.urls import reverse
import json
from django.views.decorators.csrf import csrf_exempt
import math
import requests
from django.views.decorators.http import require_POST
from web3 import Web3
from django.utils import timezone
import time
from .models import User, RidePoint, JointRide, PaymentHistory  # Removed Driver model import

# Add web3 import
try:
    from web3 import Web3, HTTPProvider
except ImportError:
    Web3 = None

def maps(request):return render(request,'maps.html')

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def geocode_city(city):
    # Append ', India' if not already present
    if ', ' not in city and 'India' not in city:
        city = f'{city}, India'
    url = f'https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1'
    headers = {'User-Agent': 'carpool-app/1.0 (contact@example.com)'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        print(f'Geocoding API response for {city}: {response.text}')
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f'Geocoding error: {e}')
    return None, None

def payment(request):
    if request.method == 'POST':
        ride_id = request.POST.get('ride_id')
        user_wallet = request.POST.get('user_wallet')
        
        try:
            ride = RidePoint.objects.get(id=ride_id)
            
            # Update ride status
            ride.status = "Ride Completed"
            ride.save()
            
            # Create or update payment history
            payment, created = PaymentHistory.objects.update_or_create(
                ride=ride,
                user_id=request.session.get('user_id'),
                defaults={
                    'transaction_hash': f"tx_{ride_id}_{int(time.time())}",
                    'amount': 0.001,  # Example amount
                    'distance': 10,   # Example distance
                    'status': 'Completed',
                    'timestamp': timezone.now()
                }
            )
            
            return render(request, 'payment.html', {
                'success': True,
                'parts': [
                    f"Transaction Hash: {payment.transaction_hash}",
                    f"Amount: {payment.amount} ETH",
                    f"Distance: {payment.distance} km",
                    f"Status: {payment.status}"
                ]
            })
            
        except (RidePoint.DoesNotExist):
            return render(request, 'payment.html', {
                'error': 'Invalid ride information'
            })
    
    # GET request - show payment form
    ride_id = request.GET.get('ride_id')
    try:
        ride = RidePoint.objects.get(id=ride_id)
        return render(request, 'payment.html', {
            'ride_id': ride_id,
        })
    except (RidePoint.DoesNotExist):
        return render(request, 'payment.html', {
            'error': 'Invalid ride information'
        })

def completed_rides(request):
    # Get user_id and user_type from Django session
    user_id = request.session.get('user_id')
    user_type = request.session.get('user_type')
    
    print(f"Completed Rides - Session data - user_id: {user_id}, user_type: {user_type}")  # Debug log
    
    # Verify user is logged in and is a passenger
    if not user_id or user_type != 'user':
        print(f"Completed Rides - Access denied - user_id: {user_id}, user_type: {user_type}")  # Debug log
        return redirect('/')
    
    # Get all completed rides for this passenger
    completed_rides = RidePoint.objects.filter(
        Q(userid=user_id) |  # Rides created by the passenger
        Q(jointride__userid=user_id)  # Rides joined by the passenger
    ).filter(
        status="Ride Completed"
    ).select_related('driverId').distinct()

    # Get driver names for all rides
    driver_ids = set(ride.driverId for ride in completed_rides if ride.driverId)
    driver_names = {str(driver.id): driver.name for driver in User.objects.filter(id__in=driver_ids)}
    
    # Add driver names and calculate distances
    for ride in completed_rides:
        ride.driver_name = driver_names.get(str(ride.driverId), 'Unknown')
        # Calculate distance if not already present
        if not hasattr(ride, 'distance'):
            from_city = ride.fromCity.strip().replace("'", "")
            to_city = ride.toCity.strip().replace("'", "")
            lat1, lon1 = geocode_city(from_city)
            lat2, lon2 = geocode_city(to_city)
            if None not in (lat1, lon1, lat2, lon2):
                ride.distance = round(haversine(lat1, lon1, lat2, lon2), 2)
                ride.eth_amount = round(ride.distance * 0.000055, 8)  # 8 decimals for ETH
            else:
                ride.distance = 0
                ride.eth_amount = 0

    # Apply sorting
    sort_by = request.GET.get('sort_by')
    if sort_by == 'distance_max_min':
        completed_rides = sorted(completed_rides, key=lambda x: x.distance, reverse=True)
    elif sort_by == 'distance_min_max':
        completed_rides = sorted(completed_rides, key=lambda x: x.distance)
    elif sort_by == 'eth_max_min':
        completed_rides = sorted(completed_rides, key=lambda x: x.eth_amount, reverse=True)
    elif sort_by == 'eth_min_max':
        completed_rides = sorted(completed_rides, key=lambda x: x.eth_amount)
    else:
        # Default sort by date
        completed_rides = sorted(completed_rides, key=lambda x: x.applyOn, reverse=True)

    return render(request, 'user/completed_rides.html', {
        'rides': completed_rides,
        'sort_by': sort_by,
        'page_title': 'Completed Rides'
    })

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
        userid = request.POST.get("userId2", 0)
        try:
            ride = RidePoint.objects.get(id=int(rideId))
            if ride:
                ride.status = "Ride Completed"
                ride.save()
                # Create a pending PaymentHistory record
                user = User.objects.get(id=int(ride.userid))
                PaymentHistory.objects.create(
                    user=user,
                    ride=ride,
                    recipient_address=ride.driver_hash or '',
                    amount=0,  # Will be updated on payment
                    tx_hash='',  # Will be updated on payment
                    distance=None,
                    status='Pending'
                )
                messages.info(request, "Ride Completed")
            else:
                messages.info(request, "Sorry Some Error In Accepting the Ride")
        except Exception as e:
            print(f"Error in stateOFCompleted: {e}")
            messages.info(request, "Sorry Some Error In Accepting the Ride")
    return redirect("acceptance",userid=userid)


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


def profiledriver(request):
    return render(request, "driver/profile.html")


def stateOF(request):
    rideId = request.POST.get("rideId", 0).strip()
    driverId = request.POST.get("driverId", "").strip()
    driver_hash = request.POST.get("driver_hash", "").strip()  # Get the ETH address
    
    print(f"Accepting ride {rideId} for driver {driverId} with wallet {driver_hash}")
    
    try:
        ride = RidePoint.objects.get(id=int(rideId))
        print(f"Found ride {rideId}. Current status: {ride.status}, current driver_hash: {ride.driver_hash}")
        
        ride.driverId = driverId
        ride.status = "Accepted By Driver"
        ride.driver_hash = driver_hash  # Save the ETH address
        ride.save()
        
        print(f"Updated ride {rideId}. New status: {ride.status}, new driver_hash: {ride.driver_hash}")
        messages.success(request, "SuccessFully Accepted")
    except RidePoint.DoesNotExist:
        print(f"Ride {rideId} not found")
        messages.error(request, "Ride not found.")
    return redirect("driverHome")


def acceptance(request,userid=0):
    data = RidePoint.objects.filter(
        Q(driverId=userid)
        & (Q(status="Accepted By Driver") | Q(status="Ride Completed"))
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
        "driver_hash",
    )
    rideDate = list(data)
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

    return render(
        request,
        "driver/accepted.html",
        context={"accepted": accepted, "completed": completed, "accepted": accepted},
    )


def driverHome(request):
    driver_id = request.session.get('user_id')
    user_type = request.session.get('user_type')
    
    print(f"DriverHome - Session data - driver_id: {driver_id}, user_type: {user_type}")  # Debug log
    
    # Verify user is logged in and is a driver
    if not driver_id or user_type != 'driver':
        print(f"DriverHome - Access denied - driver_id: {driver_id}, user_type: {user_type}")  # Debug log
        return redirect('')
    
    # Get available rides (rides without a driver)
    data = RidePoint.objects.filter(
        Q(driverId="") & ~Q(userid="")
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
    
    # Ensure session data is maintained
    request.session['user_id'] = driver_id
    request.session['user_type'] = user_type
    
    return render(request, "driver/home.html", context={"data": data})


def profileDetails(request):
    userId = request.GET.get("userid", 0)
    data = User.objects.filter(id=int(userId)).values("name", "email", "typeView")
    return JsonResponse({"profile": list(data)})


def profile(request):
    return render(request, "user/profile.html")


def getRequestFromUsers(request):
    userid = request.GET.get("userid", "")
    
    if not userid:
        return JsonResponse({"data": []})
    
    # Get all fields needed for the template
    ride_fields = [
        "id",
        "fromCity",
        "toCity",
        "datePoint",
        "contactPoint",
        "status",
        "driverId",
        "applyOn",
    ]
    
    # Get rides created by the user
    user_rides = list(RidePoint.objects.filter(userid=userid).values(*ride_fields))

    # Get rides joined by the user
    joint_rides = JointRide.objects.filter(userid=userid).values("id", "userid", "rideId")
    if joint_rides.exists():
        ride_ids = [int(d["rideId"]) for d in joint_rides]
        associated_rides = RidePoint.objects.filter(id__in=ride_ids).values(*ride_fields)
        user_rides.extend(list(associated_rides))
    
    # Sort rides by applyOn date, most recent first
    user_rides.sort(key=lambda x: x["applyOn"], reverse=True)
    
    return JsonResponse({"data": user_rides})

def addPool(request):
    user_id = request.session.get('user_id')
    user_type = request.session.get('user_type')
    
    print(f"AddPool - Session data - user_id: {user_id}, user_type: {user_type}")  # Debug log
    
    # Verify user is logged in and is a user
    if not user_id or user_type != 'user':
        print(f"AddPool - Invalid session data - user_id: {user_id}, user_type: {user_type}")  # Debug log
        return redirect('')
    
    user_pools = []
    if request.method == "POST":
        formPoint = request.POST.get("formPoint", "").strip()
        toPoint = request.POST.get("toPoint", "").strip()
        datePoint = request.POST.get("datePoint", "").strip()
        userId = request.POST.get("userId", "").strip()
        contactPoint = request.POST.get("contactPoint", "").strip()
        now = datetime.now()

        output = now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            RidePoint.objects.create(
                fromCity=formPoint,
                toCity=toPoint,
                datePoint=datePoint,
                contactPoint=contactPoint,
                status="Pending To Accept By Delivery",
                userid=userId,
                driverId="",
                applyOn=output,
            )
            messages.info(request, "Added Successfully!")
            
            # Ensure session data is maintained
            request.session['user_id'] = user_id
            request.session['user_type'] = user_type
            
            # Set session data in messages for JavaScript
            messages.info(request, f"{user_id},{user_type}")
            
            return redirect("userHome")
        except Exception as e:
            print(f"Error creating pool: {e}")
            messages.error(request, "Failed to add pool. Please try again.")
            return redirect("addPool")
    
    # For GET request
    if user_id:
        user_pools = RidePoint.objects.filter(userid=user_id)
    
    # Ensure session data is maintained
    request.session['user_id'] = user_id
    request.session['user_type'] = user_type
    
    return render(request, "user/add_pool.html", {"user_pools": user_pools})


def userHome(request):
    user_id = request.session.get('user_id')
    user_type = request.session.get('user_type')
    
    print(f"UserHome - Session data - user_id: {user_id}, user_type: {user_type}")  # Debug log
    
    # Verify user is logged in and is a user
    if not user_id or user_type != 'user':
        print(f"UserHome - Invalid session data - user_id: {user_id}, user_type: {user_type}")  # Debug log
        return redirect('')
    
    # Get pools created by the user
    created_pools = RidePoint.objects.filter(
        userid=str(user_id)
    ).exclude(
        status="Ride Completed"
    )
    
    # Get pools joined by the user through JointRide
    joined_ride_ids = JointRide.objects.filter(userid=user_id).values_list('rideId', flat=True)
    joined_pools = RidePoint.objects.filter(
        id__in=joined_ride_ids
    ).exclude(
        status="Ride Completed"
    )
    
    # Combine both querysets
    active_pools = (created_pools | joined_pools).distinct().order_by('-applyOn')
    
    print(f"UserHome - Found {active_pools.count()} active pools")  # Debug log
    
    # Get completed pools
    completed_created = RidePoint.objects.filter(
        userid=str(user_id),
        status="Ride Completed"
    )
    
    completed_joined = RidePoint.objects.filter(
        id__in=joined_ride_ids,
        status="Ride Completed"
    )
    
    completed_pools = (completed_created | completed_joined).distinct().order_by('-applyOn')
    
    print(f"UserHome - Found {completed_pools.count()} completed pools")  # Debug log

    # Get all payment records in one query
    payment_records = PaymentHistory.objects.filter(
        ride__in=list(active_pools) + list(completed_pools)
    )

    # Create a dictionary for quick payment lookup
    payment_dict = {payment.ride_id: payment for payment in payment_records}

    # Process active pools
    for pool in active_pools:
        payment = payment_dict.get(pool.id)
        pool.payment_status = payment.status if payment else "Pending"
        
        # Get driver name if available
        if pool.driverId:
            try:
                driver = User.objects.get(id=pool.driverId, typeView="driver")
                pool.driver_name = driver.name
            except User.DoesNotExist:
                pool.driver_name = "Unknown"
        else:
            pool.driver_name = "Not Assigned"

    # Process completed pools
    for pool in completed_pools:
        payment = payment_dict.get(pool.id)
        if payment:
            pool.payment_details = {
                'transaction_hash': payment.tx_hash,
                'amount': payment.amount,
                'distance': payment.distance,
                'status': payment.status,
                'timestamp': payment.timestamp
            }
        else:
            pool.payment_details = {
                'transaction_hash': 'Pending',
                'amount': 0,
                'distance': 0,
                'status': 'Pending',
                'timestamp': pool.applyOn
            }
        
        # Get driver name
        if pool.driverId:
            try:
                driver = User.objects.get(id=pool.driverId, typeView="driver")
                pool.driver_name = driver.name
            except User.DoesNotExist:
                pool.driver_name = "Unknown"
        else:
            pool.driver_name = "Not Assigned"

    # Ensure session data is maintained
    request.session['user_id'] = user_id
    request.session['user_type'] = user_type

    return render(request, 'user/home.html', {
        'active_pools': active_pools,
        'completed_pools': completed_pools
    })


def index(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        data = User.objects.filter(email=email, password=password)

        if data.exists():
            user_obj = data.last()
            request.session['user_id'] = user_obj.id  # Set user_id in session
            request.session['user_type'] = user_obj.typeView  # Set user_type in session
            print(f"User logged in - ID: {user_obj.id}, Type: {user_obj.typeView}")  # Debug log
            
            if user_obj.typeView == "driver":
                messages.success(request, "Successfully Logged in")
                messages.info(request, f"{user_obj.id},{user_obj.typeView}")
                return redirect("driverHome")
            elif user_obj.typeView == "user":
                messages.info(request, f"{user_obj.id},{user_obj.typeView}")
                messages.success(request, "Successfully Logged in")
                return redirect("userHome")
            messages.info(request, "Invalid user type")
            return redirect("")
        else:
            messages.info(request, "Invalid credentials")
            return redirect("")
    return render(request, "login.html")


def signup(request):
    if request.method == "POST":
        print("sdfsfdfl i am in ")
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        if User.objects.filter(email=email).exists():
            messages.info(request, "Try with another email !!")
            return redirect("signup")

        User.objects.create(name=name, email=email, password=password, typeView="user")
        messages.info(request, "Success")
        return redirect("")

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
        return redirect("")

    return render(request, "driverRegister.html")

def delete_pool(request, pool_id):
    user_id = request.session.get('user_id')
    try:
        pool = RidePoint.objects.get(id=pool_id, userid=str(user_id))
        pool.delete()
        messages.success(request, 'Pool deleted successfully.')
    except RidePoint.DoesNotExist:
        messages.error(request, 'Pool not found or you do not have permission to delete it.')
    return redirect('add')

@require_POST
def ajax_delete_pool(request):
    user_id = request.session.get('user_id')
    pool_id = request.POST.get('pool_id')
    if not user_id or not pool_id:
        return JsonResponse({'success': False, 'error': 'Invalid request.'})
    try:
        pool = RidePoint.objects.get(id=pool_id, userid=str(user_id))
        pool.delete()
        return JsonResponse({'success': True})
    except RidePoint.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Pool not found or permission denied.'})

def reject_pool(request):
    if request.method == "POST":
        rideId = request.POST.get("rideId", "")
        driverId = request.POST.get("driverId", "")
        try:
            ride = RidePoint.objects.get(id=int(rideId))
            ride.status = "Rejected by Driver"
            ride.driverId = driverId
            ride.save()
            messages.info(request, "Pool Rejected Successfully.")
        except RidePoint.DoesNotExist:
            messages.error(request, "Pool not found.")
    return redirect("driverHome")

def check_eth_balance(request):
    address = request.GET.get('address')
    print("Checking balance for address:", address)
    if not address:
        return JsonResponse({'success': False, 'error': 'No address provided'})
    try:
        w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
        print("Ganache connected:", w3.is_connected())
        if not w3.is_connected():
            print("Ganache not connected. Returning fake balance for demo.")
            return JsonResponse({'success': True, 'balance': '10.0'})
        balance_wei = w3.eth.get_balance(address)
        balance_eth = Web3.from_wei(balance_wei, 'ether')
        print(f"Balance for {address}: {balance_eth} ETH")
        return JsonResponse({'success': True, 'balance': str(balance_eth)})
    except Exception as e:
        print("Error while checking balance:", e)
        return JsonResponse({'success': False, 'error': str(e)})

def update_driver_wallet(request):
    driver_id = request.session.get('user_id')
    if not driver_id:
        return redirect('index')
    
    if request.method == 'POST':
        wallet_address = request.POST.get('wallet_address', '').strip()
        if wallet_address:
            # Update all rides for this driver that don't have a wallet address
            RidePoint.objects.filter(driverId=driver_id, driver_hash__isnull=True).update(driver_hash=wallet_address)
            messages.success(request, "Wallet address updated for all your rides")
        return redirect('driver_transactions')
    
    return render(request, 'driver/update_wallet.html')

def driver_transactions(request):
    driver_id = request.session.get('user_id')
    user_type = request.session.get('user_type')
    
    print(f"Driver Transactions - Session data - driver_id: {driver_id}, user_type: {user_type}")  # Debug log
    
    # Verify user is logged in and is a driver
    if not driver_id or user_type != 'driver':
        print(f"Driver Transactions - Access denied - driver_id: {driver_id}, user_type: {user_type}")  # Debug log
        return redirect('/')
    
    # Get all rides for this driver
    driver_rides = RidePoint.objects.filter(driverId=driver_id)
    print(f"Found {driver_rides.count()} rides for driver {driver_id}")
    
    # Get all ETH addresses (driver_hash) for this driver
    driver_wallets = list(driver_rides.exclude(driver_hash__isnull=True).values_list('driver_hash', flat=True).distinct())
    print(f"Driver {driver_id} wallets: {driver_wallets}")
    
    if not driver_wallets:
        print(f"No wallet addresses found for driver {driver_id}")
        return render(request, 'driver/transactions.html', {
            'payments': [],
            'error': 'No wallet addresses found. Please update your wallet address for existing rides.',
            'show_update_wallet': True,
            'page_title': 'Driver Transactions'
        })
    
    # Get all payment records for this driver's rides only
    payments = PaymentHistory.objects.filter(
        Q(ride__driverId=driver_id) &  # Only payments for rides where this driver is assigned
        Q(recipient_address__in=driver_wallets)  # Only payments to this driver's wallets
    ).select_related('user', 'ride').order_by('-timestamp')
    
    print(f"Found {payments.count()} payments for driver {driver_id}")
    
    # Add user names to payments
    user_ids = set(payment.user_id for payment in payments if payment.user_id)
    user_names = {str(user.id): user.name for user in User.objects.filter(id__in=user_ids)}
    
    # Process payments to add additional information
    processed_payments = []
    for payment in payments:
        payment.user_name = user_names.get(str(payment.user_id), 'Unknown')
        
        # Add ride details if available
        if payment.ride:
            payment.ride_details = {
                'from_city': payment.ride.fromCity,
                'to_city': payment.ride.toCity,
                'date': payment.ride.datePoint,
                'status': payment.ride.status
            }
        
        # Format amount and distance
        payment.formatted_amount = f"{payment.amount:.8f}" if payment.amount else "0.00000000"
        payment.formatted_distance = f"{payment.distance:.2f}" if payment.distance else "0.00"
        
        processed_payments.append(payment)
    
    return render(request, 'driver/transactions.html', {
        'payments': processed_payments,
        'page_title': 'Driver Transactions',
        'show_update_wallet': not driver_wallets  # Show update wallet button if no wallets found
    })

def delete_old_rides(request):
    driver_id = request.session.get('user_id')
    if not driver_id:
        return redirect('index')
    
    if request.method == 'POST':
        try:
            # Get all rides for this driver
            driver_rides = RidePoint.objects.filter(driverId=driver_id)
            
            # Get the IDs of these rides
            ride_ids = list(driver_rides.values_list('id', flat=True))
            
            # Delete associated payment history records
            PaymentHistory.objects.filter(ride_id__in=ride_ids).delete()
            
            # Delete the rides
            driver_rides.delete()
            
            messages.success(request, "All your previous rides have been deleted successfully.")
        except Exception as e:
            print(f"Error deleting rides: {e}")
            messages.error(request, "An error occurred while deleting rides.")
        
        return redirect('driver_transactions')
    
    return render(request, 'driver/delete_rides.html')

def delete_completed_rides(request):
    driver_id = request.session.get('user_id')
    if not driver_id:
        return redirect('index')
    
    if request.method == 'POST':
        try:
            # Get only completed rides for this driver
            completed_rides = RidePoint.objects.filter(
                driverId=driver_id,
                status="Ride Completed"
            )
            
            # Delete the completed rides
            count = completed_rides.count()
            completed_rides.delete()
            
            messages.success(request, f"Successfully deleted {count} completed rides.")
        except Exception as e:
            print(f"Error deleting completed rides: {e}")
            messages.error(request, "An error occurred while deleting completed rides.")
        
        return redirect('acceptance', userid=driver_id)
    
    return render(request, 'driver/delete_completed_rides.html')

def passenger_completed_rides(request):
    # Get user_id and user_type from Django session
    user_id = request.session.get('user_id')
    user_type = request.session.get('user_type')
    
    print(f"Passenger Completed Rides - Session data - user_id: {user_id}, user_type: {user_type}")  # Debug log
    
    # Verify user is logged in and is a passenger
    if not user_id or user_type != 'user':
        print(f"Passenger Completed Rides - Access denied - user_id: {user_id}, user_type: {user_type}")  # Debug log
        return redirect('/')
    
    # Get rides created by the passenger
    created_rides = RidePoint.objects.filter(
        userid=user_id,
        status="Ride Completed"
    )
    
    # Get rides joined by the passenger
    joined_ride_ids = JointRide.objects.filter(userid=user_id).values_list('rideId', flat=True)
    joined_rides = RidePoint.objects.filter(
        id__in=joined_ride_ids,
        status="Ride Completed"
    )
    
    # Combine both querysets
    completed_rides = created_rides.union(joined_rides).order_by('-applyOn')

    # Get payment details for all rides
    payment_details = {}
    for ride in completed_rides:
        payment = PaymentHistory.objects.filter(ride=ride, user_id=user_id).first()
        if payment:
            payment_details[ride.id] = {
                'tx_hash': payment.tx_hash,
                'amount': payment.amount,
                'distance': payment.distance,
                'status': payment.status,
                'timestamp': payment.timestamp
            }
        else:
            # Calculate distance and amount if no payment record exists
            from_city = ride.fromCity.strip().replace("'", "")
            to_city = ride.toCity.strip().replace("'", "")
            lat1, lon1 = geocode_city(from_city)
            lat2, lon2 = geocode_city(to_city)
            if None not in (lat1, lon1, lat2, lon2):
                distance = round(haversine(lat1, lon1, lat2, lon2), 2)
                eth_amount = round(distance * 0.000055, 8)  # 8 decimals for ETH
            else:
                distance = 0
                eth_amount = 0
            
            payment_details[ride.id] = {
                'tx_hash': 'Pending',
                'amount': eth_amount,
                'distance': distance,
                'status': 'Pending',
                'timestamp': ride.applyOn
            }

    # Get driver names for all rides
    driver_ids = set(ride.driverId for ride in completed_rides if ride.driverId)
    driver_names = {str(driver.id): driver.name for driver in User.objects.filter(id__in=driver_ids)}
    
    # Add driver names and payment details to rides
    for ride in completed_rides:
        ride.driver_name = driver_names.get(str(ride.driverId), 'Unknown')
        ride.payment_details = payment_details.get(ride.id, {})

    # Apply sorting
    sort_by = request.GET.get('sort_by')
    if sort_by == 'distance_max_min':
        completed_rides = sorted(completed_rides, key=lambda x: x.payment_details.get('distance', 0), reverse=True)
    elif sort_by == 'distance_min_max':
        completed_rides = sorted(completed_rides, key=lambda x: x.payment_details.get('distance', 0))
    elif sort_by == 'eth_max_min':
        completed_rides = sorted(completed_rides, key=lambda x: x.payment_details.get('amount', 0), reverse=True)
    elif sort_by == 'eth_min_max':
        completed_rides = sorted(completed_rides, key=lambda x: x.payment_details.get('amount', 0))
    else:
        # Default sort by date
        completed_rides = sorted(completed_rides, key=lambda x: x.payment_details.get('timestamp', x.applyOn), reverse=True)

    return render(request, 'user/completed_rides.html', {
        'rides': completed_rides,
        'sort_by': sort_by,
        'page_title': 'My Completed Rides'
    })
