from __future__ import annotations

import re
import traceback
from datetime import datetime
from string import Template
from typing import Any, Dict

from .logger import get_logger
from .path_utils import normalize_path, sanitize_path_component


class TemplateManager:
    """Manages template parsing and formatting for output paths."""

    def __init__(self) -> None:
        """Initialize the template manager with supported operations."""
        # Date operations
        self.date_operations = {
            "year": lambda dt: dt.strftime("%Y"),
            "month": lambda dt: dt.strftime("%m"),
            "day": lambda dt: dt.strftime("%d"),
            "year_month": lambda dt: dt.strftime("%Y-%m"),
            "format": lambda dt, fmt: dt.strftime(fmt.replace("%", "")),
        }

        # Define helper functions for string operations
        def sanitize_path(s: str) -> str:
            """Sanitize a string to be safe for use in file paths."""
            replacements = {
                "/": "_",  # Forward slash
                "\\": "_",  # Backslash
                ":": "-",  # Colon
                "*": "+",  # Asterisk
                "?": "",  # Question mark
                '"': "'",  # Double quote
                "<": "(",  # Less than
                ">": ")",  # Greater than
                "|": "-",  # Pipe
                "\0": "",  # Null character
                "\n": " ",  # Newline
                "\r": " ",  # Carriage return
                "\t": " ",  # Tab
            }
            result = s
            for char, replacement in replacements.items():
                result = result.replace(char, replacement)
            # Remove any leading/trailing whitespace and dots
            result = result.strip(". ")
            # Collapse multiple spaces into one
            result = " ".join(result.split())
            return result

        def get_first_word(s: str) -> str:
            """Get the first word from a string."""
            # First remove any Excel Row information
            s = re.sub(r"\s*⟨Excel Row[:-]\s*\d+⟩", "", s)
            return s.split()[0] if s else ""

        def split_by_no_get_last(s: str) -> str:
            """Split string by N° and get the last element, preserving the N° prefix."""
            # First, remove any Excel Row information
            s = re.sub(r"\s*⟨Excel Row[:-]\s*\d+⟩", "", s)

            if "N°" in s:
                parts = s.split("N°")
                return f"N°{parts[-1].strip()}"
            return s.strip()

        # String operations
        self.string_operations = {
            "upper": str.upper,
            "lower": str.lower,
            "title": str.title,
            "replace": lambda s, old, new: s.replace(old, new),
            "slice": lambda s, start, end=None: s[
                int(start) : None if end == "" else int(end)
            ],
            "sanitize": sanitize_path,
            "first_word": get_first_word,
            "split_no_last": split_by_no_get_last,
        }

    def _safe_path_component(self, value: Any) -> str:
        """Convert a value to a safe path component.

        Replaces invalid characters with underscores and ensures the result
        is a valid path component. Preserves drive letters and UNC paths.
        """
        if value is None:
            return "_"

        # Convert to string
        str_value = str(value).strip()

        # Handle empty values
        if not str_value:
            return "_"

        # Handle date values
        if isinstance(value, datetime):
            str_value = value.strftime("%Y-%m-%d")

        # Use the path_utils sanitize_path_component which preserves drive letters and UNC paths
        return sanitize_path_component(str_value)

    def _parse_field(self, field: str) -> tuple[str, list[str]]:
        """Parse a field into its name and operations.

        Args:
            field: The field string to parse

        Returns:
            A tuple containing the field name and list of operations
        """
        parts = field.split("|")
        field_name = parts[0].strip()
        operations = parts[1:] if len(parts) > 1 else []
        return field_name, operations

    def _apply_date_operation(self, date_value: datetime, operation: str) -> str:
        """Apply a date operation to a datetime value.

        Args:
            date_value: The datetime value to operate on
            operation: The operation string to apply

        Returns:
            The result of applying the date operation

        Raises:
            ValueError: If the operation format is invalid or unknown
        """
        op_parts = operation.split(".")
        if len(op_parts) != 2:
            raise ValueError(f"Invalid date operation format: {operation}")

        op_type = op_parts[1]
        if ":" in op_type:  # Handle format operation
            op_name, format_str = op_type.split(":", 1)
            if op_name not in self.date_operations:
                raise ValueError(f"Unknown date operation: {op_name}")
            return self.date_operations[op_name](date_value, format_str)
        else:
            if op_type not in self.date_operations:
                raise ValueError(f"Unknown date operation: {op_type}")
            return self.date_operations[op_type](date_value)

    def _apply_string_operation(self, value: str, operation: str) -> str:
        """Apply a string operation to a value.

        Args:
            value: The string value to operate on
            operation: The operation string to apply

        Returns:
            The result of applying the string operation

        Raises:
            ValueError: If the operation format is invalid or unknown
        """
        op_parts = operation.split(".")
        if len(op_parts) != 2:
            raise ValueError(f"Invalid string operation format: {operation}")

        op_type = op_parts[1]
        if ":" in op_type:  # Handle operations with parameters
            op_name, *params = op_type.split(":")
            if op_name not in self.string_operations:
                raise ValueError(f"Unknown string operation: {op_name}")
            return self.string_operations[op_name](value, *params)
        else:
            if op_type not in self.string_operations:
                raise ValueError(f"Unknown string operation: {op_type}")
            return self.string_operations[op_type](value)

    def _apply_operations(self, value: Any, operations: list[str]) -> str:
        """Apply a sequence of operations to a value.

        Args:
            value: The value to operate on
            operations: List of operations to apply

        Returns:
            The result of applying all operations in sequence

        Raises:
            ValueError: If an operation type is unknown or invalid for the value type
        """
        result = value
        for operation in operations:
            try:
                if operation.startswith("date."):
                    # If it's already a datetime object, use it directly
                    if isinstance(value, datetime):
                        result = self._apply_date_operation(value, operation)
                    # Otherwise try to parse it if it's a string
                    elif isinstance(value, str):
                        try:
                            # Try to parse the date string in common formats
                            for fmt in [
                                "%d_%m_%Y",
                                "%Y-%m-%d",
                                "%d/%m/%Y",
                                "%m/%d/%Y",
                                "%d-%m-%Y",
                            ]:
                                try:
                                    parsed_date = datetime.strptime(value, fmt)
                                    result = self._apply_date_operation(
                                        parsed_date, operation
                                    )
                                    break
                                except ValueError:
                                    continue
                            else:
                                # If we get here, none of the formats worked
                                logger = get_logger()
                                logger.warning(f"Could not parse date string: {value}")
                                # Use current date as fallback
                                result = self._apply_date_operation(
                                    datetime.now(), operation
                                )
                        except Exception as e:
                            logger = get_logger()
                            logger.error(f"Error in date operation: {str(e)}")
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            # Use current date as fallback
                            result = self._apply_date_operation(
                                datetime.now(), operation
                            )
                    else:
                        logger = get_logger()
                        logger.warning(
                            f"Date operations can only be applied to datetime objects or date strings: {value}"
                        )
                        # Use current date as fallback
                        result = self._apply_date_operation(datetime.now(), operation)
                elif operation.startswith("str."):
                    result = self._apply_string_operation(str(result), operation)
                else:
                    raise ValueError(f"Unknown operation type: {operation}")
            except Exception as e:
                logger = get_logger()
                logger.error(
                    f"Error applying operation '{operation}' to value '{value}': {str(e)}"
                )
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Return a safe value to continue processing
                result = str(value)

        return str(result)

    def process_template(self, template: str, data: Dict[str, Any]) -> str:
        """Process a template string using the provided data.

        Args:
            template: The template string containing fields and operations
            data: Dictionary containing the values for the template fields

        Returns:
            The processed template with all fields replaced with their processed values
        """

        def replace_field(match) -> str:
            field_content = match.group(1)
            field_name, operations = self._parse_field(field_content)

            if field_name not in data:
                logger = get_logger()
                logger.warning(f"Field not found in data: {field_name}")
                return "_"

            value = data[field_name]

            # Apply sanitization to string values except for processed_folder
            if field_name != "processed_folder" and isinstance(value, str):
                value = self.string_operations["sanitize"](value)

            # Apply operations
            try:
                return self._apply_operations(value, operations)
            except Exception as e:
                logger = get_logger()
                logger.error(f"Error processing field {field_content}: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return "_"

        # Use curly brace pattern from original implementation
        pattern = r"\{([^}]+)\}"

        # Replace all template variables
        try:
            result = re.sub(pattern, replace_field, template)
            return result
        except Exception as e:
            logger = get_logger()
            logger.error(f"Error in template processing: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return a basic fallback with the current date
            return f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def format_path(self, template: str, data: Dict[str, Any]) -> str:
        """Format a path using a template and data dictionary.

        Args:
            template: Template string with placeholders in ${name} format or {name|operation} format.
            data: Dictionary of values to substitute into the template.

        Returns:
            Formatted path string with safe path components.
        """
        try:
            # First check if the template uses the original curly brace format
            if "{" in template and "|" in template:
                # Use the original template processing logic for curly brace format
                path = self.process_template(template, data)
            else:
                # Handle the ${name} format (string.Template)
                # Convert all values to safe path components while preserving drive letters
                safe_data = {
                    key: self._safe_path_component(value) for key, value in data.items()
                }

                # Format the template
                template_obj = Template(template)
                path = template_obj.safe_substitute(safe_data)

                # Remove any remaining template variables (in case of missing data)
                while "${" in path and "}" in path:
                    start = path.find("${")
                    end = path.find("}", start) + 1
                    path = path[:start] + "_" + path[end:]

            # Normalize path using the unified path_utils.normalize_path function
            # This preserves drive letters and handles path separators correctly
            path = normalize_path(path)
            return path

        except Exception as e:
            logger = get_logger()
            logger.error(f"Error formatting path: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return a fallback path with timestamp
            return f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def validate_template(self, template: str) -> bool:
        """Validate a template string.

        Args:
            template: Template string to validate.

        Returns:
            True if the template is valid, False otherwise.
        """
        try:
            # Check for invalid path characters in the template itself
            # (excluding the variable placeholders)
            if "{" in template:  # Curly brace format
                non_var_parts = []
                current_pos = 0
                while True:
                    var_start = template.find("{", current_pos)
                    if var_start == -1:
                        non_var_parts.append(template[current_pos:])
                        break

                    non_var_parts.append(template[current_pos:var_start])
                    var_end = template.find("}", var_start)
                    if var_end == -1:
                        return False

                    current_pos = var_end + 1
            else:  # Standard ${name} format
                # Check for basic template syntax
                Template(template)

                non_var_parts = []
                current_pos = 0
                while True:
                    var_start = template.find("${", current_pos)
                    if var_start == -1:
                        non_var_parts.append(template[current_pos:])
                        break

                    non_var_parts.append(template[current_pos:var_start])
                    var_end = template.find("}", var_start)
                    if var_end == -1:
                        return False

                    current_pos = var_end + 1

            # Check each non-variable part for invalid characters
            invalid_chars = r'<>:"|?*'
            for part in non_var_parts:
                if any(char in part for char in invalid_chars):
                    return False

            return True

        except Exception as e:
            logger = get_logger()
            logger.error(f"Template validation error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
