from __future__ import annotations
from typing import Dict, Any
from string import Template
from datetime import datetime
import os

class TemplateManager:
    """Manages template parsing and formatting for output paths."""
    
    def __init__(self) -> None:
        pass
    
    @staticmethod
    def _safe_path_component(value: Any) -> str:
        """Convert a value to a safe path component.
        
        Replaces invalid characters with underscores and ensures the result
        is a valid path component.
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
        
        # Replace invalid path characters
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            str_value = str_value.replace(char, "_")
        
        # Replace multiple underscores with a single one
        while "__" in str_value:
            str_value = str_value.replace("__", "_")
        
        # Remove leading/trailing underscores
        str_value = str_value.strip("_")
        
        return str_value or "_"
    
    def format_path(self, template: str, data: Dict[str, Any]) -> str:
        """Format a path using a template and data dictionary.
        
        Args:
            template: Template string with placeholders in ${name} format.
            data: Dictionary of values to substitute into the template.
        
        Returns:
            Formatted path string with safe path components.
        """
        try:
            # Convert all values to safe path components
            safe_data = {
                key: self._safe_path_component(value)
                for key, value in data.items()
            }
            
            # Format the template
            template_obj = Template(template)
            path = template_obj.safe_substitute(safe_data)
            
            # Normalize path separators
            path = path.replace("/", os.path.sep).replace("\\", os.path.sep)
            
            # Remove any remaining template variables (in case of missing data)
            while "${" in path and "}" in path:
                start = path.find("${")
                end = path.find("}", start) + 1
                path = path[:start] + "_" + path[end:]
            
            return path
            
        except Exception as e:
            print(f"[DEBUG] Error formatting path: {str(e)}")
            raise ValueError(f"Error formatting path: {str(e)}")
    
    def validate_template(self, template: str) -> bool:
        """Validate a template string.
        
        Args:
            template: Template string to validate.
        
        Returns:
            True if the template is valid, False otherwise.
        """
        try:
            # Check for basic template syntax
            Template(template)
            
            # Check for invalid path characters in the template itself
            # (excluding the variable placeholders)
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
            
        except Exception:
            return False