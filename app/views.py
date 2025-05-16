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

def calculate_distance(lat1, lon1, lat2, lon2):
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    radius = 6371  # Earth's radius in kilometers
    distance = radius * c
    
    return round(distance, 2)

def get_coordinates(city):
    # Use Nominatim API to get coordinates
    url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json"
    headers = {'User-Agent': 'CarPool/1.0'}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"Error getting coordinates for {city}: {str(e)}")
    return None

def maps(request):return render(request,'maps.html')

def payment(request):
    ride_id = request.GET.get('rideId')
    if not ride_id:
        messages.error(request, "No ride selected for payment")
        return redirect('userHome')
        
    try:
        ride = RidePoint.objects.get(id=ride_id)
        driver = User.objects.get(id=ride.driverId)
        
        # Get coordinates for source and destination cities
        from_coords = get_coordinates(ride.fromCity)
        to_coords = get_coordinates(ride.toCity)
        
        if from_coords and to_coords:
            # Calculate actual distance using coordinates
            distance = calculate_distance(
                from_coords[0], from_coords[1],
                to_coords[0], to_coords[1]
            )
        else:
            # Fallback to default distance if coordinates not found
            distance = 50
            messages.warning(request, "Could not calculate exact distance, using default value")
            
        # Calculate fare based on distance (0.000055 ETH per km)
        fare = round(distance * 0.000055, 6)
        
        context = {
            'rideId': ride.id,
            'driverName': driver.name,
            'driverWallet': ride.payment,
            'distance': distance,
            'fare': fare,
            'fromCity': ride.fromCity,
            'toCity': ride.toCity
        }
        
        return render(request, 'payment.html', context)
    except (RidePoint.DoesNotExist, User.DoesNotExist):
        messages.error(request, "Invalid ride or driver information")
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
        userid = request.POST.get("userId2", 0)
        ride = RidePoint.objects.get(id=int(rideId))
        if ride:
            ride.status = "Ride Completed"
            ride.save()
            messages.info(request, "Ride Completed")
        else:
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
    if not request.session.get('user_id') or request.session.get('user_type') != 'driver':
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
            return redirect("driverHome")
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
    # Check if user is logged in as driver
    if not request.session.get('user_id') or request.session.get('user_type') != 'driver':
        messages.error(request, "Please login as a driver")
        return redirect('login')
        
    # Verify that the userid in URL matches the logged in user
    if str(request.session['user_id']) != str(userid):
        messages.error(request, "Unauthorized access")
        return redirect('driverHome')
        
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
        context={"accepted": accepted, "completed": completed},
    )


def driverHome(request):
    if not request.session.get('user_id') or request.session.get('user_type') != 'driver':
        messages.error(request, "Please login as a driver")
        return redirect('login')
        
    # Get rides that haven't been accepted and haven't been rejected by this driver
    data = RidePoint.objects.filter(
        Q(driverId="") & 
        ~Q(userid="") &
        ~Q(id__in=RejectedRide.objects.filter(driverId=str(request.session['user_id'])).values_list('rideId', flat=True))
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
    return render(request, "user/profile.html")


def getRequestFromUsers(request):
    userid = request.GET.get("userid", "")
    
    ride_fields = [
        "fromCity",
        "toCity",
        "datePoint",
        "contactPoint",
        "status",
        "driverId",
        "applyOn",
        "id",
    ]
    
    user_rides = list(RidePoint.objects.filter(userid=userid).values(*ride_fields))

    joint_rides = JointRide.objects.filter(userid=userid).values("id", "userid", "rideId")
    if joint_rides.exists():
        ride_ids = [int(d["rideId"]) for d in joint_rides]
        associated_rides = RidePoint.objects.filter(id__in=ride_ids).values(*ride_fields)
        user_rides.extend(list(associated_rides))
    
    return JsonResponse({"data": user_rides})

def addPool(request):
    if request.method == "POST":
        formPoint = request.POST.get("formPoint", "").strip()
        toPoint = request.POST.get("toPoint", "").strip()
        datePoint = request.POST.get("datePoint", "").strip()
        userId = request.POST.get("userId", "").strip()
        contactPoint = request.POST.get("contactPoint", "").strip()
        now = datetime.now()

        output = now.strftime("%Y-%m-%d %H:%M:%S")
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
        messages.info(request, "Added SuccessFully !!")
        return render(request, "user/add_pool.html")
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
        data = User.objects.filter(email=email, password=password)

        if data.exists():
            user = data.last()
            request.session['user_id'] = str(user.id)
            request.session['user_type'] = user.typeView
            request.session.set_expiry(86400)  # 24 hours
            
            messages.success(request, "Successfully Logged in")
            
            if user.typeView == "driver":
                return redirect("driverHome")
            elif user.typeView == "user":
                return redirect("userHome")
            
        messages.error(request, "Invalid credentials")
        return redirect("login")
        
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

def logout(request):
    request.session.flush()
    messages.success(request, "Successfully logged out")
    return redirect('login')
