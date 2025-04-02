from django.db.models.signals import post_save
from django.dispatch import receiver
from authentication.models import Mailbox
from authentication.views import calculate_shipping_price  # utility file
from decimal import Decimal

@receiver(post_save, sender=Mailbox)
def auto_calculate_shipping_price(sender, instance, created, **kwargs):
    if created and instance.shipping_price is None:
        try:
            shipping_price = calculate_shipping_price(instance)
            instance.shipping_price = shipping_price or Decimal("0.00")
            instance.save(update_fields=["shipping_price"])
        except Exception as e:
            print(f"⚠️ Shipping price calc failed for Mailbox #{instance.id}: {e}")
