from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import *
from .models import *
from django.core.mail import send_mail
from ipware import get_client_ip
import random
import string

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

    def patch(self, request, pk):
        if not request.user.is_superuser:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user.is_approved:
            return Response({"detail": "User is already approved."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate unique identifier
        unique_id = ''.join(random.choices(string.digits, k=5))
        user.unique_user_id = unique_id
        user.is_approved = True
        user.save()

        # Send account approval email
        send_mail(
            subject="Your Account Has Been Approved",
            message=f"Dear {user.username},\n\nYour account has been approved with User ID: {unique_id}. You can now log in.\n\nThank you!",
            from_email="your_email@example.com",  # Replace with your email
            recipient_list=[user.email],
        )

        return Response({"detail": f"User {user.id} approved successfully with ID {unique_id}."}, status=status.HTTP_200_OK)

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
            if new_price is not None:
                mailbox_item.product_value = new_price
                mailbox_item.save()
                return Response({"detail": "Price updated successfully."}, status=status.HTTP_200_OK)

            return Response({"detail": "Product value is required."}, status=status.HTTP_400_BAD_REQUEST)

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
            # Fetch user details
            user = User.objects.get(pk=pk, is_superuser=False)
            user_serializer = UserSerializer(user)

            # Fetch mailbox items for the user
            mailbox_items = Mailbox.objects.filter(user=user)
            mailbox_serializer = MailboxSerializer(mailbox_items, many=True)

            return Response({
                "user_details": user_serializer.data,
                "mailbox_items": mailbox_serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

class GlobalAddressView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        address = GlobalAddress.objects.first()
        if address:
            serializer = GlobalAddressSerializer(address)
            return Response(serializer.data)
        return Response({"detail": "No global address found."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        data = request.data
        GlobalAddress.objects.all().delete()  # Ensure only one global address exists
        serializer = GlobalAddressSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        address = GlobalAddress.objects.first()
        if not address:
            return Response({"detail": "No global address found to update."}, status=status.HTTP_404_NOT_FOUND)

        serializer = GlobalAddressSerializer(address, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        GlobalAddress.objects.all().delete()
        return Response({"detail": "Global address deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
