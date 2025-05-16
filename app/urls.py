from django.contrib import admin
from django.urls import path
from .views import *

urlpatterns = [
    path("maps/", view=maps, name="maps"),
    path('update_distance/', view=update_distance, name="update_distance"),
    path('payment/', view=payment, name="payment"),
    path('updateTransaction/', view=updateTransaction, name="updateTransaction"),
    path('AcceptTheRide/', view=AcceptTheRide, name="AcceptTheRide"),
    path('stateOFCompleted/', view=stateOFCompleted, name="stateOFCompleted"),
    path('getJoinPool/', view=getJoinPool, name="getJoinPool"),
    path('joinPool/', view=joinPool, name="joinPool"),
    path('stateOF/', view=stateOF, name="stateOF"),
    path('rejectRide/', view=rejectRide, name="rejectRide"),
    path('acceptance/<int:userid>/', view=acceptance, name="acceptance"),
    path('driver/transactions/', view=driverTransactions, name="driverTransactions"),
    path('profileDetails/', view=profileDetails, name="profileDetails"),
    path('profile/', view=profile, name="profile"),
    path('getRequestFromUsers/', view=getRequestFromUsers, name="getRequestFromUsers"),
    path('addPool/', view=addPool, name="add_pool"),
    path('driverHome/', view=driverHome, name="driverHome"),
    path('userHome/', view=userHome, name="userHome"),
    path("login/", view=index, name="login"),
    path("signup/", view=signup, name="signup"),
    path("dregister/", view=dregister, name="dregister"),
    path('logout/', view=logout, name="logout"),
    path('payment-success/', view=payment_success, name='payment_success'),
    path('deletePool/<int:pool_id>/', view=deletePool, name='deletePool'),
    path('get_transactions/', view=get_transactions, name='get_transactions'),
    path('clear_transactions/', view=clear_transactions, name='clear_transactions'),
    path('transaction-history/', view=transaction_history, name='transaction_history'),
    path("", view=index, name="index"),
]
