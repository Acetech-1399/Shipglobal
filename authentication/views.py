from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from authentication.serializers import UserSerializer, MailboxSerializer, GlobalAddressSerializer, AddressBookSerializer, PasswordResetSerializer, PasswordResetConfirmSerializer, ChangePasswordSerializer, BannerSerializer
from authentication.models import Mailbox,GlobalAddress,AddressBook,BlockedIP, Banner
from django.core.mail import send_mail,EmailMessage
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model
import paypalrestsdk
import logging
from .utils.invoice import generate_invoice
import math
from decimal import Decimal
from django.core.files import File
import os
from .shipping_price_calculator import load_price_slab, get_price_for_weight
from shipping.models import Shipment
from django.utils.timezone import now, timedelta
from rest_framework.parsers import MultiPartParser, FormParser
from django.template.loader import render_to_string
from weasyprint import HTML
from io import BytesIO

User = get_user_model()

def get_real_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]  # first IP is client IP
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Welcome! You are authenticated."})

def send_welcome_email(user):
    try:
        global_addresses = GlobalAddress.objects.all()
        logo_path = os.path.join(settings.MEDIA_ROOT, "images", "logo.png")

        context = {
            "first_name": user.first_name or "Valued Customer",
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or "ShipShop User",
            "unique_user_id": user.unique_user_id,
            "global_addresses": global_addresses,
            "logo_url": f"file://{logo_path}"
        }

        html_string = render_to_string("welcome_letter.html", context)
        pdf_file = BytesIO()
        HTML(string=html_string).write_pdf(pdf_file)
        pdf_file.seek(0)

        subject = "Welcome to ShipShopGlobal"
        message = f"""
        Hi {user.first_name or user.username},

        Welcome to ShipShopGlobal! Attached is your welcome letter PDF with details on how to use your shipping address.

        Thank you,
        Team ShipShopGlobal
        """

        email = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
        email.attach("ShipShopGlobal_Welcome.pdf", pdf_file.read(), "application/pdf")
        email.send()

    except Exception as e:
        print("❌ Email send failed:", e)

class RegisterView(APIView):
    def post(self, request):
        data = request.data.copy()
        client_ip = get_real_ip(request)

        # 🔐 Blocked IP check
        if BlockedIP.objects.filter(ip_address=client_ip).exists():
            return Response({"detail": "Registrations from this IP are blocked."}, status=403)

        data['email'] = data.get('email', '').lower()
        if 'username' in data:
            data['username'] = data['username'].lower()

        if User.objects.filter(email=data['email']).exists():
            return Response({"detail": "User with this email already exists."}, status=400)

        # 🔍 Suspicious check: last 10 mins, same IP
        time_threshold = now() - timedelta(minutes=10)
        users = User.objects.filter(ip_address=client_ip, date_joined__gte=time_threshold).order_by('-date_joined')

        is_suspicious = False
        if len(users) >= 2:
            try:
                time_diff = (users[0].date_joined - users[-1].date_joined).total_seconds()
                if len(users) + 1 >= 3 and time_diff <= 120:
                    is_suspicious = True
            except IndexError:
                pass

        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            user.ip_address = client_ip
            user.is_suspicious = is_suspicious
            user.save()
            # 🚫 Auto block IP if suspicious
            if is_suspicious:
                BlockedIP.objects.get_or_create(ip_address=client_ip)
            response = Response({"detail": "Registration successful."}, status=201)

            # ✉️ Then send mail
            send_welcome_email(user)

            return response
        return Response(serializer.errors, status=400)


class SuspiciousUserList(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        users = User.objects.filter(is_suspicious=True)
        data = [{"id": u.id, "username": u.username, "email": u.email, "ip": u.ip_address} for u in users]
        return Response(data)


class BlockedIPList(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        blocked = BlockedIP.objects.all().values("ip_address", "reason", "blocked_at")
        return Response(blocked)

    def delete(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            user.is_suspicious = False
            user.save()
            # Optional: unblock IP too
            BlockedIP.objects.filter(ip_address=user.ip_address).delete()
            return Response({"detail": "User and IP unblocked."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)

class GenerateUsername(APIView):
    def get(self, request):
        import random
        import string

        while True:
            username = "user_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            if not User.objects.filter(username=username).exists():
                break
        return Response({"username": username})


class AdminRegistrationView(APIView):
    def post(self, request):
        client_ip = get_real_ip(request)
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

class AdminUserShipmentListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, user_id):
        shipments = Shipment.objects.filter(user_id=user_id).order_by("-created_at")

        data = [{
            "id":s.id,
            "item_name": s.item_name,
            "product_value": s.product_value,
            "tracking_number": s.tracking_number,
            "shipping_price": s.shipping_price,
            "status": s.status,
            "weight": s.weight,
            "dimension": s.dimension,
            "invoice_url": request.build_absolute_uri(s.invoice_pdf.url) if s.invoice_pdf else None,
            "image": request.build_absolute_uri(s.image.url) if s.image else None,
            "created_at": s.created_at
        } for s in shipments]

        return Response(data, status=200)

class AdminUpdateShipmentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, shipment_id):
        try:
            shipment = Shipment.objects.get(pk=shipment_id)
            new_status = request.data.get("status")

            if new_status not in dict(Shipment._meta.get_field("status").choices):
                return Response({"detail": "Invalid status."}, status=400)

            shipment.status = new_status
            shipment.save()

            return Response({"detail": f"Shipment status updated to '{new_status}'."}, status=200)

        except Shipment.DoesNotExist:
            return Response({"detail": "Shipment not found."}, status=404)

class AdminDeleteUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def delete(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            if user.is_superuser:
                return Response({"detail": "Cannot delete an admin user."}, status=400)
            user.delete()
            return Response({"detail": "User deleted successfully."}, status=204)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)


class UserLoginView(APIView):
    def post(self, request):
        username = request.data.get("username", "").lower()
        password = request.data.get("password")

        try:
            user = User.objects.get(username=username)

            if not user.check_password(password):
                return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user_id": user.id,
                "username": user.username,
                "is_superuser": user.is_superuser,
                "unique_user_id": user.unique_user_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

class AdminLoginView(APIView):
    def post(self, request):
        client_ip = get_real_ip(request)

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
                "unique_user_id": user.unique_user_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)


def calculate_shipping_price(mailbox, slab_file_path=None):
    try:
        dims = [float(x) for x in mailbox.dimension.split("x")]
        length, width, height = dims if len(dims) == 3 else (1, 1, 1)
        volumetric_weight = (length * width * height) / 5000
        actual_weight = float(mailbox.weight)
        final_weight = max(volumetric_weight, actual_weight)
        final_weight = math.ceil(final_weight)  # always round up for slabs

        price_slab = load_price_slab(slab_file_path)
        price = get_price_for_weight(final_weight, price_slab)

        return Decimal(str(price))  # return as Decimal for DB
    except Exception as e:
        print("Shipping price calculation failed:", e)
        return Decimal("0.00")


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
            mailbox = Mailbox.objects.get(id=serializer.data["id"])
            # shipping_price = calculate_shipping_price(mailbox)  # use dummy or slab file
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            slab_file_path = os.path.join(project_root, "shipping_rates.csv")
            print("slab file path", slab_file_path)
            shipping_price = calculate_shipping_price(mailbox, slab_file_path=slab_file_path)
            mailbox.shipping_price = shipping_price
            mailbox.save()
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

class BannerUploadView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = BannerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "Banner uploaded successfully.", "data": serializer.data})
        return Response(serializer.errors, status=400)

class BannerListView(APIView):
    def get(self, request):
        banners = Banner.objects.filter(active=True)
        serializer = BannerSerializer(banners, many=True)
        return Response(serializer.data)

class AdminBannerList(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        banners = Banner.objects.all().order_by('-uploaded_at')
        serializer = BannerSerializer(banners, many=True)
        return Response(serializer.data)

class BannerDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def delete(self, request, banner_id):
        try:
            banner = Banner.objects.get(pk=banner_id)
            banner.delete()
            return Response({"detail": "Banner deleted successfully."})
        except Banner.DoesNotExist:
            return Response({"detail": "Banner not found."}, status=404)

class SetActiveBannerView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, banner_id):
        try:
            banner = Banner.objects.get(pk=banner_id)
            banner.active = not banner.active  # Toggle logic
            banner.save()
            status_str = "activated" if banner.active else "deactivated"
            return Response({"detail": f"Banner {status_str} successfully."})
        except Banner.DoesNotExist:
            return Response({"detail": "Banner not found."}, status=404)

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


# views.py


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
            item_ids = request.data.get("item_ids", [])

            if not item_ids or not isinstance(item_ids, list):
                return Response({"detail": "Invalid or missing item_ids."}, status=400)

            # Get mailbox items (for this user or for all if admin)
            if request.user.is_superuser:
                mailbox_items = Mailbox.objects.filter(id__in=item_ids)
            else:
                mailbox_items = Mailbox.objects.filter(id__in=item_ids, user=request.user)

            if not mailbox_items.exists():
                return Response({"detail": "No mailbox items found."}, status=404)

            amount = sum(float(item.shipping_price or 0) for item in mailbox_items)

            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "redirect_urls": {
                    "return_url": "https://shipshopglobal.com/payment-success",
                    "cancel_url": "https://shipshopglobal.com/payment-cancel"
                },
                "transactions": [{
                    "item_list": {
                        "items": [{
                            "name": "Mailbox Checkout",
                            "sku": "MBX001",
                            "price": "%.2f" % amount,
                            "currency": "USD",
                            "quantity": 1
                        }]
                    },
                    "amount": {
                        "total": "%.2f" % amount,
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
                        "price": str(mailbox.shipping_price),
                        "weight": mailbox.weight,
                        "dimension": mailbox.dimension,
                        "tracking_number": mailbox.tracking_number,
                    })

                # ✅ Send invoice email
                invoice_path = generate_invoice(request.user, payment_id, items)
                invoice_filename = os.path.basename(invoice_path)
                invoice_url = request.build_absolute_uri(
                    settings.MEDIA_URL + "invoices/" + invoice_filename
                )
                # Open the file and save as Django File object
                with open(invoice_path, "rb") as f:
                    invoice_file = File(f)

                    for mailbox in mailbox_items:
                        shipment = Shipment.objects.create(
                            user=mailbox.user,
                            item_name=mailbox.item_name,
                            product_value=mailbox.product_value,
                            tracking_number=mailbox.tracking_number,
                            image=mailbox.image,
                            weight=mailbox.weight,
                            dimension=mailbox.dimension,
                            shipping_price=mailbox.shipping_price,
                            status="in_transit"
                        )
                        shipment.invoice_pdf.save(invoice_filename, invoice_file, save=True)
                        mailbox.delete()

                subject = "Your Payment Invoice - ShipShopGlobal"
                message = f"Hi {request.user.username},\n\nPlease find attached your invoice for payment ID {payment_id}."
                email = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [request.user.email])
                email.attach_file(invoice_path)
                email.send()

                return Response({
                    "detail": "Payment & shipment successful!",
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


class ShippingCostByWeightView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            final_weight = request.data.get("final_weight")

            if not final_weight:
                return Response({"detail": "final_weight is required."}, status=400)

            final_weight = math.ceil(float(final_weight))  # round up for slabs
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            slab_file_path = os.path.join(project_root, "shipping_rates.csv")
            print("slab file path", slab_file_path)
            price_slab = load_price_slab(slab_file_path)
            shipping_price = get_price_for_weight(final_weight, price_slab)

            return Response({
                "final_weight": final_weight,
                "shipping_price": float(shipping_price)
            }, status=200)

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return Response({"detail": "Something went wrong.", "error": str(e)}, status=500)


