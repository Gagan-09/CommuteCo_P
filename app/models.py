from django.db import models

class User(models.Model):
    id=models.IntegerField(auto_created=True,primary_key=True)
    name=models.CharField(max_length=1000)
    email=models.CharField(max_length=1000)
    password=models.CharField(max_length=1000)
    typeView=models.CharField(max_length=1000)

class RidePoint(models.Model):
    id=models.IntegerField(auto_created=True,primary_key=True)
    fromCity=models.CharField(max_length=1000)
    toCity=models.CharField(max_length=1000)
    datePoint=models.CharField(max_length=1000)
    contactPoint=models.CharField(max_length=1000)
    status=models.CharField(max_length=1000)
    userid=models.CharField(max_length=1000)
    driverId=models.CharField(max_length=1000)
    applyOn=models.CharField(max_length=1000)
    payment=models.CharField(max_length=1000)
    driver_hash=models.CharField(max_length=100, blank=True, null=True)

class JointRide(models.Model):
    id=models.AutoField(primary_key=True)
    userid=models.CharField(max_length=1000)
    rideId=models.CharField(max_length=1000)

class PaymentHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ride = models.ForeignKey(RidePoint, on_delete=models.CASCADE, null=True, blank=True)
    recipient_address = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=18, decimal_places=8)
    tx_hash = models.CharField(max_length=100)
    distance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Pending')
                                                                                                      
