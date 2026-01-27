import frappe
import requests
import json
from arb.arb_apis.utils.frappe_configs import get_cache_timeout_minutes


def send_to_ga(city, state, country, page):
    payload = {
        "client_id": "guest_" + frappe.generate_hash(length=12),
        "events": [
            {
                "name": "guest_visit",
                "params": {
                    "page_path": page,
                    "city": city,
                    "state": state,
                    "country": country,
                    "user_type": "guest",
                },
            }
        ],
    }

    requests.post(
        "https://www.google-analytics.com/mp/collect",
        params={"measurement_id": "G-XXXXXXX", "api_secret": "GA_SECRET"},
        data=json.dumps(payload),
    )


@frappe.whitelist(allow_guest=True)
def track_guest():
    ip = frappe.local.request_ip
    page = frappe.form_dict.get("page")

    # Geo lookup (FREE / Paid)
    geo = requests.get(f"https://ipapi.co/{ip}/json/").json()

    city = geo.get("city")
    region = geo.get("region")
    country = geo.get("country_name")

    # 🔹 Save to DB (optional)
    frappe.get_doc(
        {
            "doctype": "Guest Tracking Log",
            "ip_address": ip,
            "city": city,
            "state": region,
            "country": country,
            "page": page,
        }
    ).insert(ignore_permissions=True)

    # 🔹 Send to GA4
    send_to_ga(city, region, country, page)

    return {"status": "ok"}


@frappe.whitelist(allow_guest=True)
def get_tracking_keys():
    cache_key = "tracking_settings_keys"

    # Try to get from cache
    cached_data = frappe.cache().get(cache_key)
    if cached_data:
        return cached_data

    # Fetch from database if not in cache
    doc = frappe.get_single("Tracking Settings")
    result = {
        "ga_id": doc.ga_id,
        "meta_pixel_id": doc.meta_pixel_id,
        "enable_tracking": doc.enable_tracking,
    }

    frappe.cache().set_value(cache_key, result, get_cache_timeout_minutes() * 60)

    return result
