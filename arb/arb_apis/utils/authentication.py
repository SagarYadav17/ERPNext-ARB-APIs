from datetime import datetime, timedelta, timezone
from functools import wraps
import random
import re

from arb.arb_apis.utils.frappe_configs import (
    get_jwt_algorithm,
    get_jwt_expiry_minutes,
    get_jwt_refresh_expiry_days,
    get_jwt_secret,
)
import frappe
import jwt
from frappe import _
import hashlib
import time
from contextlib import suppress


def generate_jwt_token(user_email: str) -> str:
    """
    Docstring for generate_jwt_token

    :param user_email: User's email address
    :type user_email: str
    :return: JWT Access token
    :rtype: str
    """

    secret = get_jwt_secret()
    payload = {
        "email": user_email,
        "iat": datetime.timestamp(datetime.now(timezone.utc)),
        "exp": datetime.timestamp(
            datetime.now(timezone.utc) + timedelta(minutes=get_jwt_expiry_minutes())
        ),
    }

    token = jwt.encode(payload, secret, algorithm=get_jwt_algorithm())
    return token


def generate_refresh_token(user_email: str) -> str:
    """
    Docstring for generate_refresh_token

    :param user_email: User's email address
    :type user_email: str
    :return: JWT refresh token
    :rtype: str
    """

    secret = get_jwt_secret()
    payload = {
        "email": user_email,
        "type": "refresh",
        "iat": datetime.timestamp(datetime.now(timezone.utc)),
        "exp": datetime.timestamp(
            datetime.now(timezone.utc) + timedelta(days=get_jwt_refresh_expiry_days())
        ),
    }

    token = jwt.encode(payload, secret, algorithm=get_jwt_algorithm())
    return token


def verify_jwt_token(token: str) -> dict | None:
    """
    Docstring for verify_jwt_token

    :param token: JWT token
    :type token: str
    :return: Payload if token is valid, else None
    :rtype: dict | None
    """
    with suppress(jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        secret = get_jwt_secret()
        payload = jwt.decode(token, secret, algorithms=[get_jwt_algorithm()])
        return payload

    return None


def require_jwt_auth(f):
    """
    Decorator to require JWT authentication for an endpoint.

    Usage:
        @frappe.whitelist(allow_guest=True)
        @require_jwt_auth
        def protected_endpoint():
            pass
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        token = frappe.request.headers.get("Token", "")

        if not token:
            frappe.throw(_("Missing or invalid Authorization header"))

        # Verify token
        payload = verify_jwt_token(token)
        if not payload:
            frappe.throw(_("Invalid or expired token"))

        # Set current user context
        frappe.session.user = payload.get("email")

        return f(*args, **kwargs)

    return decorated_function


def generate_otp(length: int = 6) -> str:
    """
    Generate a numeric OTP of given length.

    :param length: Length of the OTP
    :type length: int
    :return: Generated OTP
    :rtype: str

    Defaults to 6 if length is less than or equal to 0 or greater than 9.
    """

    if (length <= 0) or (length > 9):
        length = 6

    otp = ""
    # return "".join([str(random.randint(0, 9)) for _ in range(length)])
    # return "".join(random.choices("123456789", k=length))

    for _ in range(length):
        # otp += str(random.randint(1, 9))

        # temp code for developement purpose
        numbers = "123456789"
        otp = numbers[:length]

    print("Generated OTP:", otp)

    return otp


def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()

def blacklist_refresh_token(refresh_token: str):
    """
    Blacklist refresh token until it expires
    """
    frappe.cache().set_value(
        f"blacklist_refresh_{refresh_token}",
        True,
        expires_in_sec=7 * 24 * 60 * 60,  # match refresh expiry
    )


def is_refresh_token_blacklisted(refresh_token: str) -> bool:
    return bool(frappe.cache().get_value(f"blacklist_refresh_{refresh_token}"))
