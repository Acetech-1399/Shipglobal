import math
import csv
import os
from decimal import Decimal

# ✅ Dummy weight-to-price mapping
# Later: load from file
DUMMY_PRICE_SLAB = {
    0.5: 5,
    1: 8,
    2: 12,
    3: 16,
    5: 22,
    10: 35,
    20: 50,
    30: 70,
}

def load_price_slab(file_path=None):
    if not file_path:
        return DUMMY_PRICE_SLAB

    price_slab = {}
    with open(file_path, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            weight_limit = float(row[0])
            price = float(row[1])
            price_slab[weight_limit] = price
    return price_slab

def get_price_for_weight(final_weight, price_slab):
    closest = None
    for w in sorted(price_slab.keys()):
        if final_weight <= w:
            closest = w
            break
    if closest is None:
        closest = max(price_slab.keys())
    return price_slab[closest]
