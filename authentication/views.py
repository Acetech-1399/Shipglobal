from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import *
from authentication.models import Mailbox,GlobalAddress,AddressBook
from django.core.mail import send_mail
from ipware import get_client_ip
import random
import string
from django.urls import reverse
from django.conf import settings
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from django.utils import timezone
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model
import paypalrestsdk
import logging
from .utils.invoice import generate_invoice
from django.core.mail import EmailMessage
from . import paypal_config
import os


User = get_user_model()

class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Welcome! You are authenticated."})

class RegisterView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            # Generate a temporary username based on the email
            validated_data = serializer.validated_data
            validated_data["username"] = validated_data["email"].split("@")[0]
            User.objects.create_user(**validated_data)
            return Response({"detail": "Registration successful. Please wait for admin approval."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AdminUserApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        pending_users = User.objects.filter(is_approved=False).values("id", "username", "email", "is_approved")
        return Response(pending_users, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        if not request.user.is_superuser:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user.is_approved:
            return Response({"detail": "User is already approved."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_approved = True
        user.save()

        # Send account approval email
        send_mail(
            subject="Your Account Has Been Approved",
            message=f"Dear {user.username},\n\nYour account has been approved with User ID: {user.unique_user_id}. You can now log in.\n\nThank you!",
            from_email="your_email@example.com",  # Replace with your email
            recipient_list=[user.email],
        )

        return Response({"detail": f"User {user.id} approved successfully with ID {user.unique_user_id}."}, status=status.HTTP_200_OK)

class AdminRegistrationView(APIView):
    def post(self, request):
        client_ip, is_routable = get_client_ip(request)
        allowed_ip = "192.168.1.8"  # Replace with your specific IP

        if client_ip != allowed_ip:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        username = data.get("username")
        password = data.get("password")
        ip = data.get("allowed_ip", client_ip)

        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                is_superuser=True,
                allowed_ip=ip
            )
            return Response({"detail": "Admin account created successfully."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UserLoginView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        try:
            user = User.objects.get(username=username)

            if not user.is_approved:
                return Response({"detail": "Your account is not approved yet. Please wait for admin approval."}, status=status.HTTP_403_FORBIDDEN)

            if not user.check_password(password):
                return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user_id": user.id,
                "username": user.username,
                "is_superuser": user.is_superuser,
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

class AdminLoginView(APIView):
    def post(self, request):
        client_ip, is_routable = get_client_ip(request)

        username = request.data.get("username")
        password = request.data.get("password")

        try:
            user = User.objects.get(username=username)

            if not user.is_superuser:
                return Response({"detail": "Unauthorized access."}, status=status.HTTP_403_FORBIDDEN)

            if hasattr(user, "allowed_ip") and user.allowed_ip and user.allowed_ip != client_ip:
                return Response({"detail": "Access denied. IP not authorized."}, status=status.HTTP_403_FORBIDDEN)

            if not user.check_password(password):
                return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user_id": user.id,
                "username": user.username,
                "is_superuser": user.is_superuser,
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

class MailboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        mailboxes = Mailbox.objects.filter(user_id=user_id)
        serializer = MailboxSerializer(mailboxes, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        data["user"] = user.id
        serializer = MailboxSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateMailboxPriceView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            # Fetch the mailbox item
            mailbox_item = Mailbox.objects.get(pk=pk)

            # Ensure the requesting user is either the item owner or an admin
            if request.user != mailbox_item.user and not request.user.is_superuser:
                return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

            # Update the product value (price)
            new_price = request.data.get("product_value")
            new_tracking = request.data.get("tracking_number")
            weight = request.data.get("weight")
            dimension = request.data.get("dimension")

            if any(field is not None for field in [new_price, new_tracking, weight, dimension]):
                if new_price is not None:
                    mailbox_item.product_value = new_price
                if new_tracking is not None:
                    mailbox_item.tracking_number = new_tracking
                if weight is not None:
                    mailbox_item.weight = weight
                if dimension is not None:
                    mailbox_item.dimension = dimension
                mailbox_item.save()
                return Response({"detail": "Update successful."}, status=status.HTTP_200_OK)

            return Response({"detail": "At least one update value is required."}, status=status.HTTP_400_BAD_REQUEST)

        except Mailbox.DoesNotExist:
            return Response({"detail": "Mailbox item not found."}, status=status.HTTP_404_NOT_FOUND)

class DeleteMailboxView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not request.user.is_superuser:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        try:
            mailbox_item = Mailbox.objects.get(pk=pk)
            mailbox_item.delete()
            return Response({"detail": "Mailbox item deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Mailbox.DoesNotExist:
            return Response({"detail": "Mailbox item not found."}, status=status.HTTP_404_NOT_FOUND)

class Userlist(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        # Fetch all non-admin users
        non_admin_users = User.objects.filter(is_superuser=False).values("id", "username")
        return Response(non_admin_users, status=status.HTTP_200_OK)

class UserDetailsWithMailboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk, is_superuser=False)
            user_serializer = UserSerializer(user)
            mailbox_items = Mailbox.objects.filter(user=user)
            mailbox_serializer = MailboxSerializer(mailbox_items, many=True)

            # Get default address
            default_address = AddressBook.objects.filter(user=user, is_default=True).first()
            default_address_data = AddressBookSerializer(default_address).data if default_address else None

            return Response({
                "user_details": user_serializer.data,
                "default_address": default_address_data,
                "mailbox_items": mailbox_serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class GlobalAddressView(APIView):
    def get(self, request):
        # Fetch all addresses
        addresses = GlobalAddress.objects.all()
        serializer = GlobalAddressSerializer(addresses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        # Allow admin to add a new address
        serializer = GlobalAddressSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.is_superuser:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        # Allow admin to delete an address by ID
        try:
            address = GlobalAddress.objects.get(pk=pk)
            address.delete()
            return Response({"detail": "Address deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except GlobalAddress.DoesNotExist:
            return Response({"detail": "Address not found."}, status=status.HTTP_404_NOT_FOUND)

class UserAddressListForAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if not request.user.is_superuser:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        addresses = AddressBook.objects.filter(user_id=user_id)
        serializer = AddressBookSerializer(addresses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AddressBookView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = AddressBook.objects.filter(user=request.user)
        serializer = AddressBookSerializer(addresses, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AddressBookSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SetDefaultAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            address = AddressBook.objects.get(pk=pk, user=request.user)
            address.is_default = True
            address.save()
            return Response({"detail": "Default address updated."}, status=status.HTTP_200_OK)
        except AddressBook.DoesNotExist:
            return Response({"detail": "Address not found."}, status=status.HTTP_404_NOT_FOUND)

class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
            token_generator = PasswordResetTokenGenerator()
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)

            frontend_base_url = "https://shipshopglobal.com"  # Replace this with your React app URL
            reset_link = f"{frontend_base_url}/reset-password/{uid}/{token}"

            send_mail(
                subject="Password Reset Request",
                message=f"Use the link below to reset your password (valid for 15 mins):\n\n{reset_link}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
            )

            return Response({"detail": "Password reset link sent."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "Email not found."}, status=status.HTTP_404_NOT_FOUND)

class PasswordResetConfirmView(APIView):
    def post(self, request, uidb64, token):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data['password']

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        token_generator = PasswordResetTokenGenerator()

        if user and token_generator.check_token(user, token):
            user.set_password(password)
            user.save()
            return Response({"detail": "Password reset successful."}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Invalid or expired link."}, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['current_password']):
            return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


logger = logging.getLogger(__name__)

class PayPalCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            amount = "100.00"
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": "https://shipshopglobal.com/payment-success",
                    "cancel_url": "https://shipshopglobal.com/payment-cancel"
                },
                "transactions": [{
                    "item_list": {
                        "items": [{
                            "name": "Mailbox Checkout",
                            "sku": "MBX001",
                            "price": amount,
                            "currency": "USD",
                            "quantity": 1
                        }]
                    },
                    "amount": {
                        "total": amount,
                        "currency": "USD"
                    },
                    "description": "Mailbox item checkout"
                }]
            })

            if payment.create():
                for link in payment.links:
                    if link.rel == "approval_url":
                        return Response({
                            "payment_id": payment.id,
                            "approval_url": str(link.href)
                        }, status=200)
                return Response({"detail": "Approval URL not found."}, status=500)
            else:
                return Response({"detail": "PayPal creation failed", "error": payment.error}, status=500)

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return Response({"detail": "Server error", "error": str(e)}, status=500)

class PayPalExecutePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get("payment_id")
        payer_id = request.data.get("payer_id")
        item_ids = request.data.get("item_ids", [])

        try:
            payment = paypalrestsdk.Payment.find(payment_id)

            if payment.execute({"payer_id": payer_id}):
                mailbox_items = Mailbox.objects.filter(id__in=item_ids, user=request.user)
                if not mailbox_items.exists():
                    return Response({"detail": "No mailbox items found."}, status=404)

                items = []
                for mailbox in mailbox_items:
                    items.append({
                        "name": mailbox.item_name,
                        "price": str(mailbox.product_value),
                        "weight": mailbox.weight,
                        "dimension": mailbox.dimension,
                        "tracking_number": mailbox.tracking_number,
                    })

                invoice_path = generate_invoice(request.user, payment_id, items)
                invoice_url = request.build_absolute_uri(
                    settings.MEDIA_URL + "invoices/" + os.path.basename(invoice_path)
                )

                subject = "Your Payment Invoice - ShipShopGlobal"
                message = f"Hi {request.user.username},\n\nPlease find attached your invoice for payment ID {payment_id}."
                email = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [request.user.email])
                email.attach_file(invoice_path)
                email.send()

                return Response({
                    "detail": "Payment executed successfully!",
                    "invoice_url": invoice_url,
                    "payment_id": payment_id
                }, status=200)

            else:
                return Response({"detail": "Payment execution failed.", "error": payment.error}, status=500)

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return Response({"detail": "Server error", "error": str(e)}, status=500)



class MailboxCheckoutDataView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        item_ids = request.data.get("item_ids", [])

        if not item_ids or not isinstance(item_ids, list):
            return Response({"detail": "Invalid or missing item_ids."}, status=status.HTTP_400_BAD_REQUEST)

        # Only allow the logged-in user to fetch their own items unless admin
        if request.user.is_superuser:
            mailbox_items = Mailbox.objects.filter(id__in=item_ids)
        else:
            mailbox_items = Mailbox.objects.filter(id__in=item_ids, user=request.user)

        if not mailbox_items.exists():
            return Response({"detail": "No mailbox items found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = MailboxSerializer(mailbox_items, many=True)
        return Response({
            "checkout_items": serializer.data,
            "total_price": sum(item.product_value for item in mailbox_items),
            "user_id": request.user.id,
            "user_email": request.user.email,
        }, status=status.HTTP_200_OK)
