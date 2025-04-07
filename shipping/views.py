from rest_framework.response import Response
from shipping.models import Shipment
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser

# shipping/views.py or wherever you prefer
class UpdateShipmentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]  # or customize

    def patch(self, request, pk):
        try:
            shipment = Shipment.objects.get(pk=pk)
            new_status = request.data.get("status")
            carrier = request.data.get("carrier")
            tracking_url = request.data.get("carrier_tracking_url")

            if new_status:
                shipment.status = new_status
            if carrier:
                shipment.carrier = carrier
            if tracking_url:
                shipment.carrier_tracking_url = tracking_url

            shipment.save()
            return Response({"detail": "Shipment updated successfully."}, status=200)

        except Shipment.DoesNotExist:
            return Response({"detail": "Shipment not found."}, status=404)


class ShipmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_superuser:
            shipments = Shipment.objects.all()
        else:
            shipments = Shipment.objects.filter(user=request.user)

        data = [{
            "id":s.id,
            "item_name": s.item_name,
            "product_value": s.product_value,
            "tracking_number": s.tracking_number,
            "shipping_price": s.shipping_price,
            "invoice_url": request.build_absolute_uri(s.invoice_pdf.url) if s.invoice_pdf else None,
            "created_at": s.created_at,
            "image": request.build_absolute_uri(s.image.url) if s.image else None,
            "dimension": s.dimension,
            "weight": s.weight,
            "status": s.status,
            "carrier": s.carrier,
            "carrier_tracking_url": s.carrier_tracking_url,
        } for s in shipments]



        return Response(data, status=200)
