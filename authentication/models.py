from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from datetime import date

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15)
    actual_address = models.TextField()
    billing_address = models.TextField()
    date_of_birth = models.DateField(null=True, blank=True, default=None)
    is_approved = models.BooleanField(default=False)  # Approval state
    unique_user_id = models.CharField(max_length=10, blank=True, null=True)  # Admin-assigned unique ID

    groups = models.ManyToManyField(
        Group,
        related_name="custom_user_set",
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="custom_user_permissions_set",
        blank=True,
    )

    def __str__(self):
        return self.username



class Mailbox(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mailbox")
    item_name = models.CharField(max_length=100)
    product_value = models.DecimalField(max_digits=10, decimal_places=2)
    tracking_number = models.CharField(max_length=50)
    image = models.ImageField(upload_to="mailbox_images/")

    def __str__(self):
        return f"{self.item_name} ({self.user.username})"


class AdminUser(AbstractUser):
    is_admin_user = models.BooleanField(default=False)
    allowed_ip = models.GenericIPAddressField(null=True, blank=True)

    groups = models.ManyToManyField(
        Group,
        related_name="admin_user_set",  # Avoid conflict with User
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="admin_user_permissions_set",  # Avoid conflict with User
        blank=True,
    )

    def save(self, *args, **kwargs):
        if self.is_admin_user and not self.allowed_ip:
            raise ValueError("Admin users must have an allowed IP address.")
        super().save(*args, **kwargs)
