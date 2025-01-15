from django.contrib import admin
from .models import *

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "phone_number", "date_of_birth")
    search_fields = ("username", "email")

@admin.register(Mailbox)
class MailboxAdmin(admin.ModelAdmin):
    list_display = ("item_name", "product_value", "tracking_number", "user")
    search_fields = ("item_name", "tracking_number")

@admin.register(GlobalAddress)
class GlobaAddressAdmin(admin.ModelAdmin):
    list_display = ("country", "state", "zip_code", "phone")
    search_fields = ("country", "state", "zip_code")