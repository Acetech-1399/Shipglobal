from django.db import models

class MailItem(models.Model):
    name = models.CharField(max_length=100)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    tracking_number = models.CharField(max_length=100)
    image = models.ImageField(upload_to='mail_images/')
