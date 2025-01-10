from rest_framework import serializers
from .models import User, Mailbox

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "username", "email", "phone_number", "actual_address",
            "billing_address", "date_of_birth", "password", "is_approved", "unique_user_id"
        ]
        extra_kwargs = {"password": {"write_only": True}, "is_approved": {"read_only": True}, "unique_user_id": {"read_only": True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class MailboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mailbox
        fields = ["id", "user", "item_name", "product_value", "tracking_number", "image"]
    class Meta:
        model = Mailbox
        fields = ["id", "user", "item_name", "product_value", "tracking_number", "image"]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None
    
class AdminUserApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "is_approved"]