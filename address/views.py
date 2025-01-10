from rest_framework.generics import ListCreateAPIView
from .models import Address
from .serializers import AddressSerializer

class AddressView(ListCreateAPIView):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
