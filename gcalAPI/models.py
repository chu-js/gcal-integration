from django.db import models
import uuid

# Create your models here.
class AvailableSlots(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)

class Booking(models.Model):
    status = models.CharField(max_length=200)
    customer_name = models.CharField(max_length=200)
    product = models.CharField(max_length=500)
    total_price = models.FloatField()
    customer_contact_no = models.IntegerField()
    colour = models.CharField(max_length=200)
    colour_code = models.IntegerField()
    add_ons = models.CharField(max_length=500)
    additional_notes = models.CharField(max_length=500)