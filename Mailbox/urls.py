from django.urls import path
from .views import MailboxView

urlpatterns = [
    path('', MailboxView.as_view(), name='mailbox'),
]
