from django.db import models

class User(models.Model):
    id=models.IntegerField(auto_created=True,primary_key=True)
    name=models.CharField(max_length=1000)
    email=models.CharField(max_length=1000)
    password=models.CharField(max_length=1000)
    typeView=models.CharField(max_length=1000)

class Transaction(models.Model):
    id = models.AutoField(primary_key=True)
    ride = models.ForeignKey('RidePoint', on_delete=models.CASCADE)
    driver = models.ForeignKey(User, on_delete=models.CASCADE)
    source = models.CharField(max_length=1000)
    destination = models.CharField(max_length=1000)
    distance = models.FloatField()  # in kilometers
    fare = models.FloatField()  # in ETH
    transaction_hash = models.CharField(max_length=1000, blank=True, null=True)
    status = models.CharField(max_length=100, default='pending')  # pending, completed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transaction {self.id} - {self.ride.id} - {self.status}"

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
    distance=models.FloatField(null=True)  # Distance in kilometers, no default value

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

class DistanceCalculation(models.Model):
    id = models.AutoField(primary_key=True)
    distance = models.FloatField()  # Distance in kilometers
    calculated_at = models.DateTimeField(auto_now_add=True)
    ride = models.ForeignKey(RidePoint, on_delete=models.CASCADE, null=True)  # Link to the ride if available

    def __str__(self):
        return f"{self.distance} km at {self.calculated_at}"
                                                                                                      
