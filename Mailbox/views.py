from rest_framework.generics import ListCreateAPIView
from .models import MailItem
from .serializers import MailItemSerializer

class MailboxView(ListCreateAPIView):
    queryset = MailItem.objects.all()
    serializer_class = MailItemSerializer
