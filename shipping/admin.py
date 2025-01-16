from django.contrib import admin
from .models import Shipment

@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("user", "cost", "paid", "tracking_number", "status", "created_at")
    list_filter = ("paid", "status")
    search_fields = ("user__username", "tracking_number")
    actions = ["mark_as_paid", "assign_tracking"]

    def mark_as_paid(self, request, queryset):
        queryset.update(paid=True, status="Awaiting Tracking Number")
        self.message_user(request, "Selected shipments marked as paid.")

    def assign_tracking(self, request, queryset):
        # Placeholder: Add logic for assigning tracking numbers in bulk if needed
        self.message_user(request, "Tracking numbers assigned.")
