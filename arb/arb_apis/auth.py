"""
JWT Authentication API for ARB
"""

from datetime import datetime, timezone

from arb.arb_apis.schemas import (
    CheckUserExistsRequest,
    CompleteSignupRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResendIdentifierRequest,
    ResendOTPRequest,
    ResetPasswordRequest,
    SendSignupOTPRequest,
    ValidateTokenRequest,
    VerifyOTPRequest,
    VerifyResetOTPRequest,
    LogoutRequest,
)
from arb.arb_apis.utils.authentication import (
    generate_jwt_token,
    generate_otp,
    generate_refresh_token,
    hash_otp,
    require_jwt_auth,
    verify_jwt_token,
    blacklist_refresh_token,
)
from arb.arb_apis.utils.frappe_configs import (
    get_jwt_expiry_minutes,
    get_otp_expiry_minutes,
    get_otp_resend_limit_per_hour,
)
from arb.arb_apis.utils.notification_templates import (
    send_password_reset_success_email,
    send_welcome_notification,
)
from arb.arb_apis.utils.pydantic_validator import validate_request
import frappe
from frappe import _


def send_otp(purpose, identifier, extra_data=None):
    """
    purpose: signup | reset
    identifier: phone or email
    """

    otp = generate_otp()
    otp_hash = hash_otp(otp)
    expiry_minutes = get_otp_expiry_minutes()

    cache_key = f"otp_{purpose}_{identifier}"

    existing = frappe.cache().get_value(cache_key) or {}
    resend_attempts = existing.get("resend_attempts", 0)

    if existing:
        resend_attempts += 1
        if resend_attempts > get_otp_resend_limit_per_hour():
            frappe.throw(
                _("OTP resend limit exceeded. Please try again after some time.")
            )

    frappe.cache().set_value(
        cache_key,
        {
            "otp_hash": otp_hash,
            "attempts": 0,
            "resend_attempts": resend_attempts,
            "verified": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "extra": extra_data or {},
        },
        expires_in_sec=expiry_minutes * 60,
    )

    # TODO: Integrate with SMS/Email service to send the OTP

    response = {
        "status": "success",
        "message": "OTP generated successfully",
        "expires_in": expiry_minutes * 60,
    }

    frappe.logger().info(f"OTP generated for {identifier} ({purpose})")

    return response


@frappe.whitelist(allow_guest=True)
@validate_request(LoginRequest)
def login(data: LoginRequest):
    """
    Login with email or phone number
    Args:
        data: LoginRequest with username and password
    """

    try:
        # Find user by email or phone number
        user_email = None

        if "@" in data.username:
            user_list = frappe.db.get_all(
                "User", filters={"email": data.username}, fields=["name"], limit=1
            )
        else:
            user_list = frappe.db.get_all(
                "User", filters={"mobile_no": data.username}, fields=["name"], limit=1
            )

        if user_list:
            user_email = user_list[0].name

        if not user_email:
            frappe.throw(_("Invalid credentials, user not found"))

        user = frappe.get_doc("User", user_email)

        # Check if user is enabled
        if user.enabled != 1:
            frappe.throw(_("User account is disabled"))

        # Validate password
        if not frappe.utils.password.check_password(user_email, data.password):
            frappe.throw(_("Invalid credentials, incorrect password"))

        # Generate tokens
        access_token = generate_jwt_token(user_email)
        refresh_token = generate_refresh_token(user_email)

        return {
            "status": "success",
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "user": {
                "email": user.email,
                "phone": user.mobile_no,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "user_image": user.user_image,
            },
        }

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ARB Login Error")
        return {
            "status": "error",
            "message": "Authentication failed",
        }


@frappe.whitelist(allow_guest=True)
@validate_request(RefreshTokenRequest)
def refresh_token(data: RefreshTokenRequest):
    try:
        # Verify refresh token
        payload = verify_jwt_token(data.refresh_token)

        if not payload or payload.get("type") != "refresh":
            frappe.throw(_("Invalid refresh token"))

        email = payload.get("email")

        # Validate user still exists and is enabled
        if not frappe.db.exists("User", email):
            frappe.throw(_("User not found"))

        user = frappe.get_doc("User", email)
        if user.disabled:
            frappe.throw(_("User account is disabled"))

        # Generate new access token
        new_access_token = generate_jwt_token(email)

        return {
            "status": "success",
            "access_token": new_access_token,
            "token_type": "Bearer",
        }

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ARB Refresh Token Error")
        return {
            "status": "error",
            "message": "Token refresh failed",
        }


@frappe.whitelist(allow_guest=True)
@validate_request(ValidateTokenRequest)
def validate_token(data: ValidateTokenRequest):
    try:
        payload = verify_jwt_token(data.token)

        if not payload:
            return {
                "status": "invalid",
                "valid": False,
                "message": "Token is invalid or expired",
            }

        # Validate user still exists
        email = payload.get("email")
        if not frappe.db.exists("User", email):
            return {
                "status": "invalid",
                "valid": False,
                "message": "User not found",
            }

        user = frappe.get_doc("User", email)
        if user.disabled:
            return {
                "status": "invalid",
                "valid": False,
                "message": "User account is disabled",
            }

        return {
            "status": "valid",
            "valid": True,
            "email": email,
            "issued_at": datetime.fromtimestamp(payload.get("iat")).isoformat(),
            "expires_at": datetime.fromtimestamp(payload.get("exp")).isoformat(),
        }

    except Exception:
        return {
            "status": "error",
            "valid": False,
            "message": "Validation failed",
        }


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def get_current_user():
    """
    Get current logged-in user details
    """

    user_email = frappe.session.user

    if user_email == "Guest":
        return {
            "status": "error",
            "message": "No user is logged in",
        }

    user = frappe.get_doc("User", user_email)

    return {
        "status": "success",
        "user": {
            "email": user.email,
            "phone": user.mobile_no,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "user_image": user.user_image,
        },
    }


# Step 1: Send Signup OTP
@frappe.whitelist(allow_guest=True)
@validate_request(SendSignupOTPRequest)
def send_signup_otp(data: SendSignupOTPRequest):

    if frappe.db.exists("User", {"mobile_no": data.phone}):
        frappe.throw(_("Phone number already registered"))

    return send_otp(
        purpose="signup",
        identifier=data.phone,
        extra_data={"full_name": data.full_name},
    )


# Step 2: Verify OTP
@frappe.whitelist(allow_guest=True)
@validate_request(VerifyOTPRequest)
def verify_signup_otp(data: VerifyOTPRequest):
    """
    Step 2: Verify OTP for phone verification
    """
    try:
        cache_key = f"otp_signup_{data.phone}"
        otp_data = frappe.cache().get_value(cache_key)

        if not otp_data:
            frappe.throw(_("OTP expired or invalid"))

        if otp_data["attempts"] >= 3:
            frappe.throw(_("Too many attempts. Request a new OTP"))

        if hash_otp(data.otp) != otp_data["otp_hash"]:
            otp_data["attempts"] += 1
            frappe.cache().set_value(
                cache_key, otp_data, expires_in_sec=get_otp_expiry_minutes() * 60
            )
            frappe.throw(_("Invalid OTP"))

        otp_data["verified"] = True
        frappe.cache().set_value(
            cache_key, otp_data, expires_in_sec=get_otp_expiry_minutes() * 60
        )

        return {
            "status": "success",
            "message": "OTP verified successfully",
            "verified": True,
            "phone": data.phone,
            "full_name": otp_data["extra"].get("full_name"),
        }

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ARB Verify OTP Error")
        return {
            "status": "error",
            "message": "Failed to verify OTP. Please try again.",
        }


# Step 3: Complete Signup
@frappe.whitelist(allow_guest=True)
@validate_request(CompleteSignupRequest)
def complete_signup(data: CompleteSignupRequest):
    """
    Step 3: Complete signup with password
    """
    try:
        # Verify OTP was completed
        otp_key = f"otp_signup_{data.phone}"
        otp_data = frappe.cache().get_value(otp_key)

        if not otp_data or not otp_data.get("verified"):
            frappe.throw(_("Phone verification required"))

        full_name = otp_data["extra"].get("full_name", "")

        # Validate email if provided
        email = data.email
        if email and email.strip():
            email = email.strip()
            if "@" not in email or "." not in email:
                frappe.throw(_("Please enter a valid email address"))

            # Check if email exists
            if frappe.db.exists("User", {"email": email}):
                frappe.throw(
                    _(
                        "Email already registered. Please use a different email or login."
                    )
                )

        # Generate username (use phone as username)
        username = f"user_{data.phone}"

        # Generate email if not provided
        if not email:
            email = f"{data.phone}@arb.local"  # Temporary email, user can update later

        # Split full name into first and last name
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Check if user already exists (edge case)
        if frappe.db.exists("User", {"mobile_no": data.phone}):
            frappe.throw(_("Phone number already registered. Please login instead."))

        # Create new user
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "mobile_no": data.phone,
                "username": username,
                "send_welcome_email": 0,
                "user_type": "Website User",
                "enabled": 1,
                "new_password": data.password,
            }
        )

        # Insert the user
        user.insert(ignore_permissions=True)

        # Create Customer record linked to this user
        try:
            customer = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": full_name,
                    "customer_type": "Individual",
                    "customer_group": "Individual",
                    "territory": "India",
                    "mobile_no": data.phone,
                    "email_id": email if email != f"{data.phone}@arb.local" else "",
                    "lead_name": full_name,
                    "custom_user_id": user.name,  # Link user to customer
                }
            )
            customer.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(
                f"Failed to create customer for user {user.name}: {str(e)}",
                "ARB Signup",
            )

        # Commit the transaction
        frappe.db.commit()

        # Generate tokens
        access_token = generate_jwt_token(user.name)
        refresh_token = generate_refresh_token(user.name)

        # Send welcome notification
        try:
            send_welcome_notification(user.name, first_name, data.phone, email)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "ARB Welcome Notification Error")

        # Clear OTP cache
        frappe.cache().delete_key(otp_key)

        return {
            "status": "success",
            "message": "Account created successfully",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "user": {
                "email": user.email,
                "phone": user.mobile_no,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "username": user.username,
                "user_image": user.user_image,
            },
        }

    except frappe.ValidationError as e:
        frappe.db.rollback()
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "ARB Complete Signup Error")
        return {
            "status": "error",
            "message": "Failed to create account. Please try again.",
        }


# Resend OTP
@frappe.whitelist(allow_guest=True)
@validate_request(ResendOTPRequest)
def resend_signup_otp(data: ResendOTPRequest):
    """
    Resend OTP for signup
    """
    try:
        return send_otp(purpose="signup", identifier=data.phone)

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ARB Resend OTP Error")
        return {
            "status": "error",
            "message": "Failed to resend OTP. Please try again.",
        }


@frappe.whitelist(allow_guest=True)
@validate_request(ForgotPasswordRequest)
def forgot_password_request(data: ForgotPasswordRequest):
    """
    Step 1: Request password reset via phone or email
    """
    try:
        phone = data.phone
        email = data.email

        user_email = None
        user_phone = None
        user_name = None

        if phone:
            # Find user by phone
            user_list = frappe.db.get_all(
                "User",
                filters={"mobile_no": phone, "enabled": 1},
                fields=["name", "email", "mobile_no", "first_name"],
                limit=1,
            )

            if not user_list:
                frappe.throw(_("No account found with this phone number"))

            user_email = user_list[0].name
            user_phone = phone
            user_name = user_list[0].first_name

        elif email:
            # Find user by email
            if "@" not in email:
                frappe.throw(_("Please enter a valid email address"))

            user_list = frappe.db.get_all(
                "User",
                filters={"email": email, "enabled": 1},
                fields=["name", "email", "mobile_no", "first_name"],
                limit=1,
            )

            if not user_list:
                frappe.throw(_("No account found with this email address"))

            user_email = user_list[0].name
            user_phone = user_list[0].mobile_no
            user_name = user_list[0].first_name

        return send_otp(
            purpose="reset",
            identifier=user_email,
            extra_data={
                "user_email": user_email,
                "phone": user_phone,
                "name": user_name,
            },
            expiry_minutes=15,
        )

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ARB Forgot Password Request Error")
        return {
            "status": "error",
            "message": "Failed to process request. Please try again.",
        }


@frappe.whitelist(allow_guest=True)
@validate_request(VerifyResetOTPRequest)
def verify_reset_otp(data: VerifyResetOTPRequest):
    """
    Step 2: Verify OTP for password reset
    """
    try:
        identifier = data.identifier
        otp = data.otp

        # Find user by identifier (phone or email)
        user_list = None

        if len(identifier) == 10 and identifier.isdigit():
            # Phone number
            user_list = frappe.db.get_all(
                "User",
                filters={"mobile_no": identifier, "enabled": 1},
                fields=["name", "email", "mobile_no"],
                limit=1,
            )
        else:
            # Email
            user_list = frappe.db.get_all(
                "User",
                filters={"email": identifier, "enabled": 1},
                fields=["name", "email", "mobile_no"],
                limit=1,
            )

        if not user_list:
            frappe.throw(_("Account not found"))

        user_email = user_list[0].name

        # Get reset data
        reset_key = f"password_reset_{user_email}"
        reset_data = frappe.cache().get_value(reset_key)

        if not reset_data:
            frappe.throw(_("Reset request has expired. Please request again."))

        # Check attempts
        if reset_data.get("attempts", 0) >= 3:
            frappe.throw(_("Too many failed attempts. Please request a new OTP."))

        # Verify OTP
        if hash_otp(otp) != reset_data["otp_hash"]:
            reset_data["attempts"] += 1
            frappe.cache().set_value(reset_key, reset_data, expires_in_sec=15 * 60)
            frappe.throw(_("Invalid OTP"))

        # Mark as verified
        reset_data["verified"] = True
        frappe.cache().set_value(reset_key, reset_data, expires_in_sec=15 * 60)

        # Generate reset token for password change
        reset_token = frappe.generate_hash(length=32)
        reset_data["reset_token"] = reset_token
        frappe.cache().set_value(reset_key, reset_data, expires_in_sec=15 * 60)

        return {
            "status": "success",
            "message": "OTP verified successfully",
            "reset_token": reset_token,
            "user_email": user_email,
            "expires_in": get_otp_expiry_minutes() * 60,
        }

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ARB Verify Reset OTP Error")
        return {
            "status": "error",
            "message": "Failed to verify OTP. Please try again.",
        }


@frappe.whitelist(allow_guest=True)
@validate_request(ResetPasswordRequest)
def reset_password(data: ResetPasswordRequest):
    """
    Step 3: Reset password with verified token
    """
    try:
        reset_token = data.reset_token
        new_password = data.new_password

        # Find user with this reset token
        user_email = None
        reset_key = None

        # Search all reset keys to find matching token
        # Note: This is simplified. In production, you might want to store token-user mapping
        # For now, we'll check all password_reset_* keys
        cache_keys = frappe.cache().get_keys("password_reset_*")

        for key in cache_keys:
            reset_data = frappe.cache().get_value(key)
            if reset_data and reset_data.get("reset_token") == reset_token:
                if reset_data.get("verified"):
                    user_email = reset_data.get("user_email")
                    reset_key = key
                    break

        if not user_email:
            frappe.throw(_("Invalid or expired reset token"))

        # Get user
        user = frappe.get_doc("User", user_email)

        # Update password
        frappe.utils.password.update_password(user_email, new_password)

        # Clear reset data
        frappe.cache().delete_key(reset_key)

        # Log password reset
        frappe.logger().info(f"Password reset for user: {user_email}")

        # Send notification
        send_password_reset_success_email(user.email, user.first_name)

        return {
            "status": "success",
            "message": "Password reset successfully",
            "user_email": user_email,
            "user_name": user.first_name,
        }

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ARB Reset Password Error")
        return {
            "status": "error",
            "message": "Failed to reset password. Please try again.",
        }


@frappe.whitelist(allow_guest=True)
@validate_request(ResendIdentifierRequest)
def resend_reset_otp(data: ResendIdentifierRequest):
    """
    Resend reset OTP
    """
    try:
        identifier = data.identifier

        # Find user
        user = frappe.db.get_value(
            "User",
            ({"email": identifier} if "@" in identifier else {"mobile_no": identifier}),
            ["name"],
            as_dict=True,
        )

        if not user:
            frappe.throw(_("Account not found"))

        return send_otp(purpose="reset", identifier=user["name"], expiry_minutes=15)

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ARB Resend Reset OTP Error")
        return {
            "status": "error",
            "message": "Failed to resend OTP. Please try again.",
        }


@frappe.whitelist(allow_guest=True)
@validate_request(VerifyOTPRequest)
def verify_login_otp(data: VerifyOTPRequest):
    key = f"otp_login_{data.phone}"
    cached = frappe.cache().get_value(key)

    if not cached:
        frappe.throw(_("OTP expired"))

    if cached.get("attempts", 0) >= 3:
        frappe.throw(_("Too many attempts. Request a new OTP"))

    if hash_otp(data.otp) != cached["otp_hash"]:
        cached["attempts"] = cached.get("attempts", 0) + 1
        frappe.cache().set_value(
            key, cached, expires_in_sec=get_otp_expiry_minutes() * 60
        )
        frappe.throw(_("Invalid OTP"))

    user_email = cached.get("extra", {}).get("user_email")
    if not user_email:
        frappe.throw(_("Account not found"))

    if not frappe.db.exists("User", {"name": user_email, "enabled": 1}):
        frappe.throw(_("Account not found or disabled"))

    frappe.cache().delete_key(key)

    access = generate_jwt_token(user_email)
    refresh = generate_refresh_token(user_email)

    return {"status": "success", "access_token": access, "refresh_token": refresh}


@frappe.whitelist(allow_guest=True)
@validate_request(ResendOTPRequest)
def send_login_otp(data: ResendOTPRequest):
    user = frappe.db.get_value(
        "User",
        {"mobile_no": data.phone, "enabled": 1},
        ["name", "email", "mobile_no"],
        as_dict=True,
    )

    if not user:
        frappe.local.response.http_status_code = 404
        return {
            "status": "error",
            "message": "Account not found",
        }

    return send_otp(
        purpose="login",
        identifier=data.phone,
        extra_data={"user_email": user["name"]},
    )

@frappe.whitelist(allow_guest=True)
@require_jwt_auth
@validate_request(LogoutRequest)
def logout(data: LogoutRequest):
    """
    Logout user
    - Blacklists refresh token
    - Clears frappe user context
    """

    try:
        # Validate refresh token
        payload = verify_jwt_token(data.refresh_token)
        if not payload or payload.get("type") != "refresh":
            frappe.throw(_("Invalid refresh token"))

        # Blacklist refresh token
        blacklist_refresh_token(data.refresh_token)

        # Clear frappe session context
        frappe.set_user("Guest")
        frappe.session.user = "Guest"

        frappe.logger().info("User logged out successfully")

        return {
            "status": "success",
            "message": "Logged out successfully",
        }

    except frappe.ValidationError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ARB Logout Error")
        return {
            "status": "error",
            "message": "Logout failed",
        }
