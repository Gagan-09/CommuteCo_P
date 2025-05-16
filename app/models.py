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

class JointRide(models.Model):
    id=models.AutoField(primary_key=True)
    userid=models.CharField(max_length=1000)
    rideId=models.CharField(max_length=1000)

class RejectedRide(models.Model):
    id = models.AutoField(primary_key=True)
    rideId = models.CharField(max_length=1000)
    driverId = models.CharField(max_length=1000)
    rejectedAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('rideId', 'driverId')
                                                                                                      
