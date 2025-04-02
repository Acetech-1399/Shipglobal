import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.exceptions import ValidationError

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15)
    is_approved = models.BooleanField(default=False)  # Approval state
    unique_user_id = models.CharField(max_length=10, blank=True, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_suspicious = models.BooleanField(default=False)
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

    def save(self, *args, **kwargs):
        # Automatically generate a unique ID if not provided
        if not self.unique_user_id:
            self.unique_user_id = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    def clean(self):
        """
        Custom validation to ensure unique_user_id remains unique.
        """
        super().clean()
        if self.unique_user_id and User.objects.filter(unique_user_id=self.unique_user_id).exclude(pk=self.pk).exists():
            raise ValidationError("A user with this unique_user_id already exists.")

    def __str__(self):
        return self.username

class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.CharField(max_length=255, default="Suspicious activity")
    blocked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ip_address

class AddressBook(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='address_book')
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set other addresses as not default
            AddressBook.objects.filter(user=self.user, is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.address_line_1}, {self.city}, {self.country}"



class Mailbox(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mailbox")
    item_name = models.CharField(max_length=100)
    product_value = models.DecimalField(max_digits=10, decimal_places=2)
    tracking_number = models.CharField(max_length=50, blank=True, null=True)
    image = models.ImageField(upload_to="mailbox_images/")
    weight = models.CharField(max_length=100)
    dimension = models.CharField(max_length=100)
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    label_pdf = models.FileField(upload_to="labels/", null=True, blank=True)
    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)



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


class GlobalAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="global_addresses", null=True, blank=True)
    country = models.CharField(max_length=100)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.address_line_1}, {self.city}, {self.state}, {self.zip_code}"

class Banner(models.Model):
    image = models.ImageField(upload_to="banners/")
    title = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"Banner {self.id}"