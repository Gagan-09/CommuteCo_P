from django.contrib import admin
from django.urls import path
from .views import *

urlpatterns = [
    path("maps/", view=maps, name="maps"),

    path('payment/', view=payment, name="payment"),
    path('AcceptTheRide/', view=AcceptTheRide, name="AcceptTheRide"),
    path('stateOFCompleted/', view=stateOFCompleted, name="stateOFCompleted"),
    path('getJoinPool/', view=getJoinPool, name="getJoinPool"),
    path('joinPool/', view=joinPool, name="joinPool"),
    path('profiledriver/', view=profiledriver, name="profiledriver"),
    path('stateOF/', view=stateOF, name="stateOF"),
    path('rejectRide/', view=rejectRide, name="rejectRide"),
    path('acceptance/<int:userid>/', view=acceptance, name="acceptance"),
    path('profileDetails/', view=profileDetails, name="profileDetails"),
    path('profile/', view=profile, name="profile"),
    path('getRequestFromUsers/', view=getRequestFromUsers, name="getRequestFromUsers"),
    path('addPool/', view=addPool, name="add"),
    path('driverHome/', view=driverHome, name="driverHome"),
    path('userHome/', view=userHome, name="userHome"),
    path("login/", view=index, name="login"),
    path("signup/", view=signup, name="signup"),
    path("dregister/", view=dregister, name="dregister"),
    path('logout/', view=logout, name="logout"),
    path("", view=index, name="index"),
]
