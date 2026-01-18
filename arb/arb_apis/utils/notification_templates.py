import frappe


def send_welcome_notification(username, first_name, phone, email):
	"""
	Send welcome notification to new user
	"""
	subject = "Welcome to ARB - India's B2B Electronics Marketplace!"

	message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="margin: 0; font-size: 28px;">Welcome to ARB!</h1>
            <p style="margin: 10px 0 0; font-size: 16px; opacity: 0.9;">India's Leading B2B Electronics Marketplace</p>
        </div>

        <div style="padding: 30px; background: #f9fafb; border-radius: 0 0 10px 10px;">
            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                Hi <strong>{first_name}</strong>,
            </p>

            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                Congratulations! Your account has been successfully created on ARB.
            </p>

            <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #e5e7eb;">
                <h3 style="margin: 0 0 15px 0; color: #111827;">Your Account Details:</h3>
                <ul style="margin: 0; padding-left: 20px; color: #4b5563;">
                    <li><strong>Phone:</strong> +91 {phone}</li>
                    <li><strong>Email:</strong> {email}</li>
                </ul>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{frappe.utils.get_url()}/login" style="background: #10b981; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">
                    Start Shopping Now
                </a>
            </div>

            <p style="font-size: 14px; color: #6b7280; line-height: 1.6;">
                Get ready to explore thousands of electronic products at wholesale prices, connect with verified suppliers, and grow your business with ARB.
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="font-size: 14px; color: #6b7280; margin: 5px 0;">
                    Need help? Contact our support team at support@arb.com or call +91 1800-XXX-XXX
                </p>
            </div>
        </div>

        <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
            <p style="margin: 5px 0;">© 2024 ARB Electronics Marketplace. All rights reserved.</p>
            <p style="margin: 5px 0;">This is an automated email, please do not reply.</p>
        </div>
    </div>
    """

	# Send email
	if email and email != f"{phone}@arb.local":
		frappe.sendmail(recipients=email, subject=subject, message=message, now=True, delayed=False)


def send_password_reset_email(email, otp, user_name):
	"""
	Send password reset OTP via email
	"""
	subject = "ARB - Password Reset Request"

	message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="margin: 0; font-size: 28px;">Password Reset Request</h1>
        </div>

        <div style="padding: 30px; background: #f9fafb; border-radius: 0 0 10px 10px;">
            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                Hi <strong>{user_name}</strong>,
            </p>

            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                We received a request to reset your password for your ARB account.
                Use the OTP below to complete the process:
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <div style="background: white; padding: 20px; border-radius: 10px; display: inline-block; border: 2px dashed #10b981; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                    <div style="font-size: 32px; font-weight: bold; letter-spacing: 10px; color: #111827;">
                        {otp}
                    </div>
                </div>
            </div>

            <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="font-size: 14px; color: #6b7280; margin: 0; text-align: center;">
                    <strong>Important:</strong> This OTP will expire in 15 minutes.
                </p>
            </div>

            <p style="font-size: 14px; color: #6b7280; line-height: 1.6;">
                If you didn't request a password reset, please ignore this email or contact our support team immediately at <a href="mailto:support@arb.com" style="color: #10b981; text-decoration: none;">support@arb.com</a>
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="font-size: 14px; color: #6b7280; margin: 5px 0;">
                    Need help? Contact our support team at support@arb.com
                </p>
            </div>
        </div>
    </div>
    """

	frappe.sendmail(recipients=email, subject=subject, message=message, now=True, delayed=False)


def send_password_reset_success_email(email, user_name):
	"""
	Send password reset success notification
	"""
	subject = "ARB - Password Reset Successful"

	message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; color: white; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="margin: 0; font-size: 28px;">Password Reset Successful</h1>
        </div>

        <div style="padding: 30px; background: #f9fafb; border-radius: 0 0 10px 10px;">
            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                Hi <strong>{user_name}</strong>,
            </p>

            <div style="background: #d1fae5; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #a7f3d0;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <svg style="width: 24px; height: 24px; color: #059669;" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <p style="font-size: 16px; color: #065f46; margin: 0; font-weight: 600;">
                        Your password has been successfully reset
                    </p>
                </div>
            </div>

            <p style="font-size: 14px; color: #6b7280; line-height: 1.6;">
                If you did not make this change or believe your account has been compromised, please contact our support team immediately at
                <a href="mailto:support@arb.com" style="color: #10b981; text-decoration: none;">support@arb.com</a>
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{frappe.utils.get_url()}/login" style="background: #10b981; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">
                    Login to Your Account
                </a>
            </div>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="font-size: 12px; color: #9ca3af; margin: 5px 0; text-align: center;">
                    For security reasons, this email cannot be replied to.
                </p>
            </div>
        </div>
    </div>
    """

	frappe.sendmail(recipients=email, subject=subject, message=message, now=True, delayed=False)
