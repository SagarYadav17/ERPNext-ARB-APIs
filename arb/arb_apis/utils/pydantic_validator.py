"""
Pydantic validation utilities for Frappe APIs
"""

from functools import wraps
from typing import TypeVar

import frappe
from frappe import _
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def validate_request(schema: type[T]):
	"""
	Decorator to validate Frappe API requests using Pydantic schemas

	Usage:
	    @frappe.whitelist(allow_guest=True)
	    @validate_request(LoginRequest)
	    def login(data: LoginRequest):
	        # data is now a validated Pydantic model
	        username = data.username
	        password = data.password
	        ...
	"""

	def decorator(f):
		@wraps(f)
		def wrapper(*args, **kwargs):
			# Get request data from Frappe
			if frappe.request and frappe.request.method == "POST":
				request_data = frappe.form_dict
			else:
				request_data = kwargs

			# Validate using Pydantic schema
			try:
				validated_data = schema(**request_data)
			except ValidationError as e:
				# Format Pydantic validation errors
				errors = []

				for error in e.errors():
					field = " -> ".join(str(loc) for loc in error["loc"])
					message = error["msg"]
					errors.append(f"{field}: {message}")

				error_message = "; ".join(errors)

				frappe.local.response.http_status_code = 400
				return {
					"status": "error",
					"message": error_message,
					"validation_errors": [
						{
							"field": " -> ".join(str(loc) for loc in err["loc"]),
							"message": err["msg"],
						}
						for err in e.errors()
					],
				}

			# Pass validated data to the function
			# Let any exceptions from the function itself propagate naturally
			return f(validated_data, *args)

		return wrapper

	return decorator
