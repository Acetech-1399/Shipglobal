from rest_framework import serializers
from .models import *
from django.contrib.auth.password_validation import validate_password
import re

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = [
            "id", "username", "email", "phone_number", "first_name", "last_name",
            "password", "is_approved", "unique_user_id", "ip_address", "is_suspicious"
        ]
        extra_kwargs = {
            "password": {"write_only": True},
            "is_approved": {"read_only": True},
            "unique_user_id": {"read_only": True},
            "ip_address": {"read_only": True},
            "is_suspicious": {"read_only": True},
        }
    def validate_password(self, value):
        errors = []
        if len(value) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not re.search(r'[A-Z]', value):
            errors.append("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            errors.append("Password must contain at least one lowercase letter.")
        if not re.search(r'\d', value):
            errors.append("Password must contain at least one digit.")
        if not re.search(r'[@$!%*?&#^]', value):
            errors.append("Password must contain at least one special character (@$!%*?&#^).")
        if errors:
            raise serializers.ValidationError(errors)
        # You can additionally use Django’s built-in validators
        validate_password(value)
        return value

    def get_is_ip_blocked(self, obj):
        from authentication.models import BlockedIP
        return BlockedIP.objects.filter(ip_address=obj.ip_address).exists()

    def validate_email(self, value):
        return value.lower()

    def create(self, validated_data):
        validated_data['email'] = validated_data['email'].lower()
        return User.objects.create_user(**validated_data)

    def get_global_address(self, obj):
        address = GlobalAddress.objects.first()
        return address.address if address else None

    def get_global_address(self, obj):
        address = GlobalAddress.objects.first()
        return address.address if address else None


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ['id', 'image', 'title', 'active', 'uploaded_at']

# serializers.py

class BrandLogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandLogo
        fields = ['id', 'image', 'title', 'active', 'uploaded_at']


class MailboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mailbox
        fields = ["id", "user", "item_name", "product_value", "tracking_number", "image", "weight", "dimension", "shipping_price"]
    class Meta:
        model = Mailbox
        fields = ["id", "user", "item_name", "product_value", "tracking_number", "image", "weight", "dimension", "shipping_price"]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None

class AdminUserApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "is_approved"]


class GlobalAddressSerializer(serializers.ModelSerializer):
    unique_user_id = serializers.SerializerMethodField()

    class Meta:
        model = GlobalAddress
        fields = [
            "id", "user", "country", "address_line_1", "address_line_2",
            "city", "state", "zip_code", "phone", "unique_user_id"
        ]

    def get_unique_user_id(self, obj):
        return obj.user.unique_user_id if obj.user else None



class AddressBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddressBook
        fields = [
            "id", "user", "address_line_1", "address_line_2", "city",
            "state", "country", "zip_code", "is_default"
        ]
        extra_kwargs = {
            "user": {"read_only": True}
        }

    def create(self, validated_data):
        user = self.context["request"].user
        is_default = validated_data.get("is_default", False)

        # If it's being marked as default, unset any other default addresses
        if is_default:
            AddressBook.objects.filter(user=user, is_default=True).update(is_default=False)

        validated_data["user"] = user
        return super().create(validated_data)

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        validate_password(value)
        # Custom regex validation (at least one uppercase, lowercase, digit, special character, and min 8 chars)
        regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#^])[A-Za-z\d@$!%*?&#^]{8,}$'
        if not re.match(regex, value):
            raise serializers.ValidationError(
                "Password must contain at least 8 characters, including uppercase, lowercase, numbers, and special characters."
            )
        return value

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_new_password(self, value):
        validate_password(value)
        regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#^])[A-Za-z\d@$!%*?&#^]{8,}$'
        if not re.match(regex, value):
            raise serializers.ValidationError(
                "Password must contain at least 8 characters, including uppercase, lowercase, numbers, and special characters."
            )
        return value