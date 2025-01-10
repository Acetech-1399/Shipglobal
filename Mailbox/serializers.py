from rest_framework import serializers
from .models import MailItem

class MailItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailItem
        fields = '__all__'
