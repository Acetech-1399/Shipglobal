from django.utils.deprecation import MiddlewareMixin
from ipware import get_client_ip

class IPTrackingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        client_ip, is_routable = get_client_ip(request)
        request.client_ip = client_ip
