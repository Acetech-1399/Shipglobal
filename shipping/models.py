from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# models.py

class Shipment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=100)
    product_value = models.DecimalField(max_digits=10, decimal_places=2)
    tracking_number = models.CharField(max_length=50)
    image = models.ImageField(upload_to="shipment_images/", null=True, blank=True)  # ✅ new
    weight = models.CharField(max_length=100, null=True, blank=True)                # ✅ new
    dimension = models.CharField(max_length=100, null=True, blank=True)            # ✅ new
    label_pdf = models.FileField(upload_to="labels/")
    invoice_pdf = models.FileField(upload_to="invoices/")
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item_name} - {self.tracking_number}"
