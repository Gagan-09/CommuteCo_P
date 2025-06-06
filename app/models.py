from django.db import models
from django.utils import timezone

class User(models.Model):
    id=models.IntegerField(auto_created=True,primary_key=True)
    name=models.CharField(max_length=100)
    email=models.CharField(max_length=100)
    password=models.CharField(max_length=100)
    typeView=models.CharField(max_length=100)
    gender=models.CharField(max_length=10, null=True, blank=True)  # For storing gender (Male/Female)
    emergency_contact_name = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_email = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_mobile = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.name

class Transaction(models.Model):
    id = models.AutoField(primary_key=True)
    ride = models.ForeignKey('RidePoint', on_delete=models.CASCADE)
    driver = models.ForeignKey(User, on_delete=models.CASCADE)
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    distance = models.DecimalField(max_digits=10, decimal_places=2)
    fare = models.DecimalField(max_digits=10, decimal_places=6)
    transaction_hash = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    passenger_count = models.IntegerField(default=0)  # Number of passengers for this transaction
    is_carpool = models.BooleanField(default=False)  # Whether this was a carpool ride

    def __str__(self):
        return f"Transaction {self.id} - {self.ride.id} - {self.status}"

class RideDistance(models.Model):
    id = models.AutoField(primary_key=True)
    ride = models.OneToOneField('RidePoint', on_delete=models.CASCADE, related_name='ride_distance')
    distance = models.FloatField()  # in kilometers
    fare = models.FloatField()  # in ETH
    calculated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Distance for Ride #{self.ride.id}: {self.distance} km"

class RidePoint(models.Model):
    id = models.IntegerField(auto_created=True, primary_key=True)
    fromCity = models.CharField(max_length=100)
    toCity = models.CharField(max_length=100)
    datePoint = models.CharField(max_length=100)
    journey_time = models.CharField(max_length=100, default="")  # New field for journey time
    contactPoint = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, default="")  # New field for phone number
    status = models.CharField(max_length=100)
    userid = models.CharField(max_length=100)
    driverId = models.CharField(max_length=100, default="")
    applyOn = models.CharField(max_length=100)
    payment = models.CharField(max_length=100)
    passenger_count = models.IntegerField(default=0)  # Track number of passengers
    is_carpool = models.BooleanField(default=False)  # True if 2 passengers, False if 1
    base_fare = models.FloatField(default=0)
    current_fare = models.FloatField(default=0)
    women_only = models.BooleanField(default=False)  # True if the ride is women-only

    def __str__(self):
        return f"Ride from {self.fromCity} to {self.toCity} on {self.datePoint}"

class JointRide(models.Model):
    id=models.AutoField(primary_key=True)
    userid=models.CharField(max_length=100)
    rideId=models.CharField(max_length=100)
    email = models.EmailField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    payment_status = models.CharField(max_length=20, default='pending')  # pending, completed
    payment_amount = models.DecimalField(max_digits=10, decimal_places=6, default=0)  # Individual payment amount
    joined_at = models.DateTimeField(default=timezone.now)  # Track when passenger joined

    def __str__(self):
        return f"Joint Ride {self.id} - User {self.userid} - Ride {self.rideId}"

class RejectedRide(models.Model):
    id = models.AutoField(primary_key=True)
    rideId = models.CharField(max_length=1000)
    driverId = models.CharField(max_length=1000)
    rejectedAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('rideId', 'driverId')

    def __str__(self):
        return f"Rejected Ride #{self.rideId} by Driver {self.driverId}"

class DistanceCalculation(models.Model):
    id = models.AutoField(primary_key=True)
    distance = models.FloatField()  # Distance in kilometers
    calculated_at = models.DateTimeField(auto_now_add=True)
    ride = models.ForeignKey(RidePoint, on_delete=models.CASCADE, null=True)  # Link to the ride if available

    def __str__(self):
        return f"{self.distance} km at {self.calculated_at}"
                                                                                                      
