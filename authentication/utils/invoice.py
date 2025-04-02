from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from django.conf import settings
import os
from datetime import datetime


def generate_invoice(user, payment_id, items):
    invoice_dir = os.path.join(settings.MEDIA_ROOT, "invoices")
    os.makedirs(invoice_dir, exist_ok=True)

    file_path = os.path.join(invoice_dir, f"invoice_{payment_id}.pdf")
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    # === Header ===
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(colors.HexColor("#333366"))
    c.drawString(50, height - 50, "ShipShopGlobal")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawRightString(width - 50, height - 50, f"Invoice Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    c.setStrokeColor(colors.gray)
    c.line(50, height - 60, width - 50, height - 60)

    # === User & Payment Info ===
    y = height - 100
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Customer Information")
    c.setFont("Helvetica", 11)
    y -= 20
    c.drawString(50, y, f"Username: {user.username}")
    y -= 15
    c.drawString(50, y, f"User ID: {user.unique_user_id}")
    y -= 15
    c.drawString(50, y, f"Email: {user.email}")
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Payment ID: {payment_id}")

    # === Item Table ===
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Purchased Items")

    # Table Headers
    y -= 20
    c.setFillColor(colors.HexColor("#f0f0f0"))
    c.rect(50, y - 5, width - 100, 20, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(55, y, "Item")
    c.drawString(220, y, "Price")
    c.drawString(300, y, "Weight")
    c.drawString(370, y, "Dimension")
    c.drawString(470, y, "Tracking #")

    # Table Rows
    c.setFont("Helvetica", 10)
    y -= 25
    total_amount = 0

    for item in items:
        c.drawString(55, y, item["name"])
        c.drawString(220, y, f"${item['price']}")
        c.drawString(300, y, f"{item['weight']} kg")
        c.drawString(370, y, item["dimension"])
        c.drawString(470, y, item["tracking_number"] or "-")
        total_amount += float(item["price"])
        y -= 20

        if y < 100:
            c.showPage()
            y = height - 50

    # === Total Section ===
    y -= 10
    c.setStrokeColor(colors.gray)
    c.line(50, y, width - 50, y)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Total Amount Paid: ${round(total_amount, 2):.2f}")

    # === Footer ===
    y -= 50
    c.setFont("Helvetica-Oblique", 10)
    c.setFillColor(colors.gray)
    c.drawString(50, y, "Thank you for shopping with ShipShopGlobal. Have a great day!")

    c.save()
    return file_path
