from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os
from django.conf import settings

def generate_invoice(user, payment_id, items):
    from reportlab.lib.units import inch

    invoice_dir = os.path.join(settings.MEDIA_ROOT, "invoices")
    os.makedirs(invoice_dir, exist_ok=True)

    file_path = os.path.join(invoice_dir, f"invoice_{payment_id}.pdf")
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "ShipShopGlobal - Invoice")

    c.setFont("Helvetica", 12)
    c.drawString(50, 720, f"Username: {user.username}")
    c.drawString(50, 700, f"User ID: {user.unique_user_id}")
    c.drawString(50, 680, f"Payment ID: {payment_id}")

    y = 640
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Purchased Items:")
    c.setFont("Helvetica", 11)

    y -= 20
    for item in items:
        c.drawString(60, y, f"- {item['name']}")
        y -= 15
        c.drawString(80, y, f"Price: ${item['price']}")
        y -= 15
        c.drawString(80, y, f"Weight: {item['weight']} kg | Dimension: {item['dimension']}")
        y -= 15
        c.drawString(80, y, f"Tracking #: {item['tracking_number']}")
        y -= 25
        if y < 100:
            c.showPage()
            y = 750

    c.drawString(50, y, "Thank you for using ShipShopGlobal!")
    c.save()

    return file_path
