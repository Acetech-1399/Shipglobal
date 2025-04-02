from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.exceptions import AuthenticationFailed
from django.http import JsonResponse

class CustomAuthExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except (InvalidToken, TokenError, AuthenticationFailed):
            return JsonResponse({
                "detail": "Token has expired",
                "code": "token_not_valid"
            }, status=401)
