from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Shipment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)  # Track payment status
    tracking_number = models.CharField(max_length=50, blank=True, null=True)  # Set by admin
    status = models.CharField(max_length=50, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Shipment for {self.user.username} - Status: {self.status}"
