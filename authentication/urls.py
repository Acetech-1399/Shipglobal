from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("admin/users/", AdminUserApprovalView.as_view(), name="admin-user-approval"),
    path("admin/users/<int:pk>/", AdminUserApprovalView.as_view(), name="admin-user-approve"),
    path("admin/register/", AdminRegistrationView.as_view(), name="admin-register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("admin/login/", AdminLoginView.as_view(), name="admin-login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("protected/", ProtectedView.as_view(), name="protected"),
    path("mailbox/<int:user_id>/", MailboxView.as_view(), name="mailbox-list"),
    path("mailbox/create/", MailboxView.as_view(), name="mailbox-create"),
    path("user_list/", Userlist.as_view(), name="user_list"),
    path("user-details/<int:pk>/", UserDetailsWithMailboxView.as_view(), name="user-details"),
    path("mailbox/update-price/<int:pk>/", UpdateMailboxPriceView.as_view(), name="update-mailbox-price"),
    path("global-address/", GlobalAddressView.as_view(), name="global-address-list"),
    path("global-address/<int:pk>/", GlobalAddressView.as_view(), name="global-address-detail"),
]