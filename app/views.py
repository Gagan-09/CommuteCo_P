from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib import messages
from .models import *
from datetime import datetime
from django.db.models import Q
from django.urls import reverse
import json
def maps(request):return render(request,'maps.html')

def payment(request):return render(request,'payment.html')

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
    rideId = request.POST.get("rideId", 0).strip()
    driverId = request.POST.get("driverId", "").strip()
    RidePoint.objects.filter(id=int(rideId)).update(
        driverId=driverId, status="Accepted By Driver"
    )
    messages.success(request, "SuccessFully Accepted")

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
    data = RidePoint.objects.filter(Q(driverId="") & ~Q(userid="")).values(
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
    return render(request, "user/home.html")


def index(request):

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        data = User.objects.filter(email=email, password=password)

        if data:
            if data.exists():
                if data.last().typeView == "driver":
                    messages.success(request, "SuccessFully Loggedin")
                    messages.info(request, f"{data.last().id},{data.last().typeView}")
                    return redirect("driverHome")
                elif data.last().typeView == "user":
                    messages.info(request, f"{data.last().id},{data.last().typeView}")
                    messages.success(request, "SuccessFully Loggedin")
                    return redirect("userHome")
                messages.info(request, "Invalid Character Involved as a user")
                return redirect("")

        messages.info(request, "Invalid user")
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
