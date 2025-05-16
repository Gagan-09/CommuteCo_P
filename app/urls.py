from django.contrib import admin
from django.urls import path
from .views import *

urlpatterns = [
    path("maps/", view=maps, name="maps"),

    path('payment/',view=payment,name="payment"),
    path('AcceptTheRide/',view=AcceptTheRide,name="AcceptTheRide"),
    path('stateOFCompleted/',view=stateOFCompleted,name="stateOFCompleted"),
    path('getJoinPool/',view=getJoinPool,name="getJoinPool"),
    path('joinPool/',view=joinPool,name="joinPool"),
    path('profiledriver/',view=profiledriver,name="profiledriver"),
    path('stateOF/',view=stateOF,name="stateOF"),
    path('acceptance/<int:userid>/',view=acceptance,name="acceptance"),
    path('profileDetails/',view=profileDetails,name="profileDetails"),
    path('profile/',view=profile,name="profile"),
    path('getRequestFromUsers/',view=getRequestFromUsers,name="getRequestFromUsers"),
    path('addPool/',view=addPool,name="add"),
    path('driverHome/',view=driverHome,name="driverHome"),
    path('userHome/',view=userHome,name="userHome"),
    path("", view=index, name=""),
    path("signup/", view=signup, name="signup"),
    path("dregister/", view=dregister, name="dregister"),
    path('completed_rides/', view=passenger_completed_rides, name='completed_rides'),
    path('delete_pool/<int:pool_id>/', view=delete_pool, name='delete_pool'),
    path('ajax_delete_pool/', view=ajax_delete_pool, name='ajax_delete_pool'),
    path('reject_pool/', view=reject_pool, name='reject_pool'),
    path('check_eth_balance/', view=check_eth_balance, name='check_eth_balance'),
    path('driver_transactions/', view=driver_transactions, name='driver_transactions'),
    path('update_driver_wallet/', view=update_driver_wallet, name='update_driver_wallet'),
    path('delete_old_rides/', view=delete_old_rides, name='delete_old_rides'),
    path('delete_completed_rides/', view=delete_completed_rides, name='delete_completed_rides'),
]
