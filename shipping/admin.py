from django.contrib import admin
from shipping.models import Shipment

@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("user", "item_name", "product_value", "tracking_number", "shipping_price", "created_at")
    search_fields = ("user__username", "tracking_number")

