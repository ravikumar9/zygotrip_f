# core/api_validators.py - API input validation for GET/POST parameters

from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError


class APIValidationError(Exception):
    """Raised when API input validation fails"""
    pass


class APIInputValidator:
    """Validate and sanitize API input parameters"""
    
    @staticmethod
    def validate_integer(value, min_value=None, max_value=None, param_name='value'):
        """
        Validate integer input.
        
        Args:
            value: Input value (can be string)
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            param_name: Parameter name for error messages
        
        Returns:
            int: Validated integer
        
        Raises:
            APIValidationError: If validation fails
        """
        if value is None or value == '':
            raise APIValidationError(f"{param_name} is required")
        
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise APIValidationError(f"{param_name} must be an integer, got '{value}'")
        
        if min_value is not None and int_value < min_value:
            raise APIValidationError(f"{param_name} must be >= {min_value}")
        
        if max_value is not None and int_value > max_value:
            raise APIValidationError(f"{param_name} must be <= {max_value}")
        
        return int_value
    
    @staticmethod
    def validate_decimal(value, min_value=None, max_value=None, param_name='value'):
        """
        Validate decimal input.
        
        Args:
            value: Input value (can be string)
            min_value: Minimum allowed value (Decimal)
            max_value: Maximum allowed value (Decimal)
            param_name: Parameter name for error messages
        
        Returns:
            Decimal: Validated decimal
        
        Raises:
            APIValidationError: If validation fails
        """
        if value is None or value == '':
            raise APIValidationError(f"{param_name} is required")
        
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError):
            raise APIValidationError(f"{param_name} must be a valid number, got '{value}'")
        
        if min_value is not None and decimal_value < min_value:
            raise APIValidationError(f"{param_name} must be >= {min_value}")
        
        if max_value is not None and decimal_value > max_value:
            raise APIValidationError(f"{param_name} must be <= {max_value}")
        
        return decimal_value
    
    @staticmethod
    def validate_choice(value, allowed_choices, param_name='value'):
        """
        Validate that value is in allowed choices.
        
        Args:
            value: Input value
            allowed_choices: List/tuple of allowed values
            param_name: Parameter name for error messages
        
        Returns:
            str: Validated choice
        
        Raises:
            APIValidationError: If validation fails
        """
        if value is None or value == '':
            raise APIValidationError(f"{param_name} is required")
        
        value_str = str(value).strip().lower()
        
        allowed_lower = [str(c).lower() for c in allowed_choices]
        if value_str not in allowed_lower:
            raise APIValidationError(
                f"{param_name} must be one of: {', '.join(str(c) for c in allowed_choices)}, got '{value}'"
            )
        
        return value_str
    
    @staticmethod
    def validate_string(value, min_length=None, max_length=None, param_name='value'):
        """
        Validate string input.
        
        Args:
            value: Input value
            min_length: Minimum string length
            max_length: Maximum string length
            param_name: Parameter name for error messages
        
        Returns:
            str: Validated and stripped string
        
        Raises:
            APIValidationError: If validation fails
        """
        if value is None:
            raise APIValidationError(f"{param_name} is required")
        
        value_str = str(value).strip()
        
        if min_length is not None and len(value_str) < min_length:
            raise APIValidationError(
                f"{param_name} must be at least {min_length} characters"
            )
        
        if max_length is not None and len(value_str) > max_length:
            raise APIValidationError(
                f"{param_name} must be at most {max_length} characters"
            )
        
        return value_str
    
    @staticmethod
    def validate_multiple_choices(values, allowed_choices, param_name='values'):
        """
        Validate multiple choices from a list.
        
        Args:
            values: List of values or comma-separated string
            allowed_choices: List/tuple of allowed values
            param_name: Parameter name for error messages
        
        Returns:
            list: Validated choices
        
        Raises:
            APIValidationError: If validation fails
        """
        # Handle comma-separated or list input
        if isinstance(values, str):
            values = [v.strip() for v in values.split(',')]
        elif not isinstance(values, (list, tuple)):
            values = [values]
        
        if not values:
            raise APIValidationError(f"{param_name} cannot be empty")
        
        # Validate each choice
        validated = []
        allowed_lower = {str(c).lower(): c for c in allowed_choices}
        
        for value in values:
            value_lower = str(value).strip().lower()
            if value_lower not in allowed_lower:
                raise APIValidationError(
                    f"{param_name} contains invalid value '{value}'"
                )
            validated.append(value_lower)
        
        return validated
    
    @staticmethod
    def validate_filter_params(filters, allowed_fields, allowed_choices):
        """
        Validate filter parameters from GET request.
        
        Args:
            filters: dict of filter parameters
            allowed_fields: dict of field_name -> validator_type
            allowed_choices: dict of field_name -> list of allowed values
        
        Returns:
            dict: Validated filters
        
        Raises:
            APIValidationError: If validation fails
        """
        validated = {}
        
        for field, value in filters.items():
            if not value or value == '':
                continue
            
            # Check if field is allowed
            if field not in allowed_fields:
                raise APIValidationError(f"Unknown filter field: '{field}'")
            
            # Validate based on type
            field_type = allowed_fields[field]
            
            if field_type == 'int':
                validated[field] = APIInputValidator.validate_integer(
                    value, param_name=field
                )
            elif field_type == 'decimal':
                validated[field] = APIInputValidator.validate_decimal(
                    value, param_name=field
                )
            elif field_type == 'choice':
                allowed = allowed_choices.get(field, [])
                validated[field] = APIInputValidator.validate_choice(
                    value, allowed, param_name=field
                )
            elif field_type == 'string':
                validated[field] = APIInputValidator.validate_string(
                    value, param_name=field
                )
            elif field_type == 'multi_choice':
                allowed = allowed_choices.get(field, [])
                validated[field] = APIInputValidator.validate_multiple_choices(
                    value, allowed, param_name=field
                )
        
        return validated


def safe_get_filter_params(request, allowed_fields, allowed_choices=None):
    """
    Safely extract and validate filter parameters from GET request.
    
    Args:
        request: Django request object
        allowed_fields: dict of allowed fields and their types
        allowed_choices: dict of allowed choices for choice fields
    
    Returns:
        dict: Validated filter parameters
    
    Raises:
        APIValidationError: If validation fails
    """
    allowed_choices = allowed_choices or {}

    try:
        return APIInputValidator.validate_filter_params(
            request.GET.dict(),
            allowed_fields,
            allowed_choices
        )
    except APIValidationError:
        raise
    except Exception as e:
        raise APIValidationError(f"Filter validation error: {str(e)}")


# ======================================================
# DJANGO REST FRAMEWORK - STANDARDISED EXCEPTION HANDLER
# ======================================================

def drf_exception_handler(exc, context):
    """
    Standardised DRF exception handler.

    All API errors return a consistent envelope:
    {
        "success": false,
        "error": {
            "code": "validation_error",
            "message": "...",
            "detail": { ... }   # optional field-level errors
        }
    }
    """
    import logging
    from rest_framework.views import exception_handler
    from rest_framework.response import Response
    from rest_framework import status

    logger = logging.getLogger('zygotrip.api')

    # Call the default DRF handler first to get a Response object
    response = exception_handler(exc, context)

    if response is not None:
        # Reshape existing DRF error responses to our envelope format
        original_data = response.data
        code = getattr(exc, 'default_code', 'error')

        if isinstance(original_data, dict) and 'detail' in original_data:
            message = str(original_data['detail'])
            detail = None
        elif isinstance(original_data, list):
            message = '; '.join(str(e) for e in original_data)
            detail = None
        else:
            message = 'Validation failed'
            detail = original_data

        response.data = {
            'success': False,
            'error': {
                'code': code,
                'message': message,
                'detail': detail,
            }
        }
        logger.warning(
            "API error: status=%s code=%s message=%s",
            response.status_code, code, message,
        )
    else:
        # Unhandled exception — return 500 with our envelope
        logger.exception("Unhandled API exception", exc_info=exc)
        response = Response(
            {
                'success': False,
                'error': {
                    'code': 'internal_error',
                    'message': 'An unexpected error occurred. Please try again later.',
                    'detail': None,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
