import requests
import stripe
import xml.etree.ElementTree as ET
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from .models import Shipment

stripe.api_key = settings.STRIPE_SECRET_KEY

class CostCalculatorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        weight = data.get("weight")
        length = data.get("length")
        width = data.get("width")
        height = data.get("height")
        destination_country = data.get("destination_country")

        if not all([weight, length, width, height, destination_country]):
            return Response({"error": "All fields are required"}, status=400)

        # ShipGlobal API credentials
        username = "your_shipglobal_username"
        password = "your_shipglobal_password"
        security_key = "your_shipglobal_security_key"
        authorize_code = "your_shipglobal_authorize_code"
        account_number = "your_shipglobal_account_number"

        # ShipGlobal API URL
        api_url = "https://www.shipglobal.us/api/testshipmentprocess"

        xml_request = f"""
        <FFUSACourier action='Request' version='1.0'>
            <Requestor>
                <Username>{username}</Username>
                <Password>{password}</Password>
                <SecurityKey>{security_key}</SecurityKey>
                <AuthorizeCode>{authorize_code}</AuthorizeCode>
                <AccountNumber>{account_number}</AccountNumber>
            </Requestor>
            <Shipments>
                <Shipment>
                    <Details>
                        <ServiceType>O</ServiceType>
                        <CustomerReference>Customer</CustomerReference>
                        <ShipmentReference>ShipRef</ShipmentReference>
                        <CustomsReference>IOSSNum</CustomsReference>
                    </Details>
                    <Packages>
                        <NumberOfPackages>1</NumberOfPackages>
                        <Package>
                            <SequenceNumber>1</SequenceNumber>
                            <PackageType>P</PackageType>
                            <Weight>{weight}</Weight>
                            <WeightType>LB</WeightType>
                            <Length>{length}</Length>
                            <Width>{width}</Width>
                            <Height>{height}</Height>
                            <DimUnit>IN</DimUnit>
                            <CustomsValue>10</CustomsValue>
                            <Currency>USD</Currency>
                        </Package>
                    </Packages>
                </Shipment>
            </Shipments>
        </FFUSACourier>
        """

        headers = {"Content-Type": "application/xml"}

        response = requests.post(api_url, data=xml_request, headers=headers)
        
        if response.status_code != 200:
            return Response({"error": "Failed to fetch shipping cost"}, status=500)

        root = ET.fromstring(response.content)
        tracking_number = root.find(".//TrackingNumber").text

        return Response({
            "estimated_cost": "10.00 USD",
            "tracking_number": tracking_number
        })

class CreateStripeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        amount = request.data.get("amount")

        if not amount:
            return Response({"error": "Amount is required"}, status=400)

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {"name": "Shipping Fee"},
                            "unit_amount": int(float(amount) * 100),
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url="https://yourfrontend.com/payment-success",
                cancel_url="https://yourfrontend.com/payment-failed",
            )
            return Response({"session_id": session.id, "url": session.url})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class ConfirmPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")

        if not session_id:
            return Response({"error": "Session ID is required"}, status=400)

        try:
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == "paid":
                user = request.user
                tracking_number = f"SG{user.id}{int(session.amount_total)}"

                # Save order details
                shipment = Shipment.objects.create(
                    user=user,
                    tracking_number=tracking_number,
                    cost=session.amount_total / 100,  # Convert cents to USD
                    status="Paid",
                )

                return Response({
                    "message": "Payment successful",
                    "tracking_number": tracking_number,
                })
            else:
                return Response({"error": "Payment not confirmed"}, status=400)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
