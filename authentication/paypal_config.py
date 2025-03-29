# paypal_config.py
import paypalrestsdk

paypalrestsdk.configure({
    "mode": "sandbox",  # or "live" when going live
    "client_id": "AagGRnlFDB8vfT4jRquVPeVS4ODxJW7oGU09Zk6Dfn7UF4ks6vuUXZcA09rKZG_8AWUuV7sTgxw7Bbmq",
    "client_secret": "EBQ-ab-fDJ_xb2hakPiETIsweV0agqzwWpPVR9WZKDNz40FwWcoLVKX_VkzIX2DD4JmS1o_PQQE0NQwJ"
})
