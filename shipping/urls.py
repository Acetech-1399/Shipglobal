from django.urls import path
from .views import CostCalculatorView, CreateStripeSessionView, ConfirmPaymentView

urlpatterns = [
    path("cost-calculator/", CostCalculatorView.as_view(), name="cost_calculator"),
    path("create-stripe-session/", CreateStripeSessionView.as_view(), name="create_stripe_session"),
    path("confirm-payment/", ConfirmPaymentView.as_view(), name="confirm_payment"),
]
