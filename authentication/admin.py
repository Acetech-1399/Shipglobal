from django.contrib import admin
from .models import Mailbox, AddressBook, GlobalAddress, User, Banner,BlockedIP, BrandLogo


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "phone_number")
    search_fields = ("username", "email")

@admin.register(Banner)
class Banner(admin.ModelAdmin):
    list_display = ("id", "image", "active")

@admin.register(BrandLogo)
class BrandLogo(admin.ModelAdmin):
    list_display = ("id", "image", "active")

@admin.register(Mailbox)
class MailboxAdmin(admin.ModelAdmin):
    list_display = ("item_name", "product_value", "tracking_number", "user")
    search_fields = ("item_name", "tracking_number")

@admin.register(GlobalAddress)
class GlobaAddressAdmin(admin.ModelAdmin):
    list_display = ("country", "state", "zip_code", "phone")
    search_fields = ("country", "state", "zip_code")

@admin.register(AddressBook)
class AddressBookAdmin(admin.ModelAdmin):
    list_display = ("user", "address_line_1", "state", "zip_code", "city")
    search_fields = ("country", "state", "zip_code", "user")

@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ("ip_address","reason")
    search_fields = ("ip_address","blocked_at")