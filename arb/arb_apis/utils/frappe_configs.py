import frappe

ARB_JWT_SECRET = "arb_jwt_secret"
ARB_OTP_EXPIRY_MINUTES = "arb_otp_expiry_minutes"
ARB_JWT_ALGORITHM = "arb_jwt_algorithm"
ARB_JWT_EXPIRY_MINUTES = "arb_jwt_expiry_minutes"
ARB_JWT_REFRESH_EXPIRY_DAYS = "arb_jwt_refresh_expiry_days"
ARB_OTP_RESEND_LIMIT_PER_HOUR = "arb_otp_resend_limit_per_hour"


def get_jwt_secret() -> str:
	return frappe.conf.get(ARB_JWT_SECRET, "your-secret-key-change-in-production")


def get_otp_expiry_minutes() -> int:
	return frappe.conf.get(ARB_OTP_EXPIRY_MINUTES, 10)


def get_jwt_algorithm() -> str:
	return frappe.conf.get(ARB_JWT_ALGORITHM, "HS256")


def get_jwt_expiry_minutes() -> int:
	return frappe.conf.get(ARB_JWT_EXPIRY_MINUTES, 60)


def get_jwt_refresh_expiry_days() -> int:
	return frappe.conf.get(ARB_JWT_REFRESH_EXPIRY_DAYS, 7)


def get_otp_resend_limit_per_hour() -> int:
	return frappe.conf.get(ARB_OTP_RESEND_LIMIT_PER_HOUR, 5)
