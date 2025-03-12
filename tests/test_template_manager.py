import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from datetime import datetime
from src.utils.template_manager import TemplateManager

class TestTemplateManager(unittest.TestCase):
    """Test cases for TemplateManager functionality."""
    
    def setUp(self):
        """Set up each test."""
        self.manager = TemplateManager()
        self.test_data = {
            "filter1": "Category",
            "filter2": "Subcategory",
            "date": datetime(2025, 3, 12),
            "id": "12345",
            "empty": "",
            "none": None,
        }
    
    def test_safe_path_component(self):
        """Test safe path component conversion."""
        test_cases = [
            # (input, expected_output)
            ("normal text", "normal text"),
            ("text/with/slashes", "text_with_slashes"),
            ("text\\with\\backslashes", "text_with_backslashes"),
            ('text"with"quotes', "text_with_quotes"),
            ("text<with>brackets", "text_with_brackets"),
            ("text:with:colons", "text_with_colons"),
            ("text?with*wildcards", "text_with_wildcards"),
            ("", "_"),
            (None, "_"),
            ("   ", "_"),
            ("multiple___underscores", "multiple_underscores"),
            ("_leading_underscore_", "leading_underscore"),
        ]
        
        for input_value, expected in test_cases:
            result = self.manager._safe_path_component(input_value)
            self.assertEqual(
                result,
                expected,
                f"Failed for input '{input_value}': expected '{expected}', got '{result}'"
            )
    
    def test_date_formatting(self):
        """Test date value formatting."""
        date = datetime(2025, 3, 12)
        result = self.manager._safe_path_component(date)
        self.assertEqual(result, "2025-03-12")
    
    def test_template_formatting(self):
        """Test template string formatting."""
        test_cases = [
            # (template, expected_output)
            (
                "${filter1}/${filter2}",
                f"Category{os.path.sep}Subcategory"
            ),
            (
                "${date}/${filter1}/${id}",
                f"2025-03-12{os.path.sep}Category{os.path.sep}12345"
            ),
            (
                "prefix_${filter1}_suffix",
                "prefix_Category_suffix"
            ),
            (
                "${empty}",
                "_"
            ),
            (
                "${none}",
                "_"
            ),
            (
                "static/path/component",
                f"static{os.path.sep}path{os.path.sep}component"
            ),
        ]
        
        for template, expected in test_cases:
            result = self.manager.format_path(template, self.test_data)
            self.assertEqual(
                result,
                expected,
                f"Failed for template '{template}': expected '{expected}', got '{result}'"
            )
    
    def test_missing_variables(self):
        """Test handling of missing template variables."""
        result = self.manager.format_path("${missing}/${filter1}", self.test_data)
        self.assertEqual(result, f"_{os.path.sep}Category")
    
    def test_validate_template(self):
        """Test template validation."""
        valid_templates = [
            "${filter1}/${filter2}",
            "prefix_${var}_suffix",
            "${var1}/${var2}/${var3}",
            "static/path/${var}",
            "${var}",
        ]
        
        invalid_templates = [
            "${unclosed",
            "invalid<chars>${var}",
            "${var}:invalid",
            'path"with"quotes/${var}',
            "path?with*wildcards/${var}",
            "${var}/path|with|pipes",
        ]
        
        for template in valid_templates:
            self.assertTrue(
                self.manager.validate_template(template),
                f"Template should be valid: {template}"
            )
        
        for template in invalid_templates:
            self.assertFalse(
                self.manager.validate_template(template),
                f"Template should be invalid: {template}"
            )
    
    def test_path_normalization(self):
        """Test path separator normalization."""
        test_cases = [
            # (template, expected)
            (
                "${filter1}/${filter2}",
                f"Category{os.path.sep}Subcategory"
            ),
            (
                "${filter1}\\${filter2}",
                f"Category{os.path.sep}Subcategory"
            ),
            (
                "mixed/path\\separators/${filter1}",
                f"mixed{os.path.sep}path{os.path.sep}Category"
            ),
        ]
        
        for template, expected in test_cases:
            result = self.manager.format_path(template, self.test_data)
            self.assertEqual(
                result,
                expected,
                f"Failed path normalization for '{template}'"
            )
    
    def test_invalid_path_characters(self):
        """Test handling of invalid path characters in values."""
        data = {
            "invalid": "value<with>invalid:chars?*",
        }
        
        result = self.manager.format_path("${invalid}", data)
        self.assertEqual(result, "value_with_invalid_chars__")
    
    def test_empty_template(self):
        """Test handling of empty template."""
        result = self.manager.format_path("", self.test_data)
        self.assertEqual(result, "")

if __name__ == '__main__':
    unittest.main()