from rest_framework import serializers
from .models import AvailableSlots

# Fix this after creating model
class AvailableSlotsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailableSlots
        fields = '__all__'