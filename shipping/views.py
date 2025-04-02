from rest_framework.response import Response
from shipping.models import Shipment
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

class ShipmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_superuser:
            shipments = Shipment.objects.all()
        else:
            shipments = Shipment.objects.filter(user=request.user)

        data = [{
          "item_name": s.item_name,
          "product_value": s.product_value,
          "tracking_number": s.tracking_number,
          "shipping_price": s.shipping_price,
          "label_url": request.build_absolute_uri(s.label_pdf.url) if s.label_pdf else None,
          "invoice_url": request.build_absolute_uri(s.invoice_pdf.url) if s.invoice_pdf else None,
          "created_at": s.created_at,
          "image": request.build_absolute_uri(s.image.url) if s.image else None,
          "dimension": s.dimension
        } for s in shipments]


        return Response(data, status=200)
