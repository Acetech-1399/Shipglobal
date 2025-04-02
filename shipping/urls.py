from django.urls import path
from . import views  # ya jo bhi correct import ho

urlpatterns = [
    # Example path
    path("shipments/", views.ShipmentListView.as_view(), name="shipment-list"),
]
