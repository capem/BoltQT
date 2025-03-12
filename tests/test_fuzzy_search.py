import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from PyQt6.QtWidgets import QApplication
from src.ui.fuzzy_search import FuzzySearchFrame

class TestFuzzySearch(unittest.TestCase):
    """Test cases for FuzzySearch functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Create the application for GUI tests."""
        cls.app = QApplication([])
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the application."""
        cls.app.quit()
    
    def setUp(self):
        """Set up each test."""
        self.test_values = [
            "Apple",
            "Banana",
            "Cherry",
            "Date",
            "Elderberry",
        ]
        self.fuzzy = FuzzySearchFrame(values=self.test_values)
    
    def test_exact_match(self):
        """Test exact match gets 100% score."""
        self.fuzzy.entry.setText("Apple")
        self.fuzzy._update_listbox()
        self.assertEqual(self.fuzzy.listbox.count(), 1)
        self.assertEqual(self.fuzzy.listbox.item(0).text(), "Apple")
    
    def test_prefix_match(self):
        """Test prefix match gets high score."""
        self.fuzzy.entry.setText("Ban")
        self.fuzzy._update_listbox()
        self.assertEqual(self.fuzzy.listbox.count(), 1)
        self.assertEqual(self.fuzzy.listbox.item(0).text(), "Banana")
    
    def test_contains_match(self):
        """Test contains match gets medium score."""
        self.fuzzy.entry.setText("berry")
        self.fuzzy._update_listbox()
        self.assertEqual(self.fuzzy.listbox.count(), 1)
        self.assertEqual(self.fuzzy.listbox.item(0).text(), "Elderberry")
    
    def test_fuzzy_match(self):
        """Test fuzzy matching with typos."""
        self.fuzzy.entry.setText("Banan")  # Missing 'a'
        self.fuzzy._update_listbox()
        self.assertEqual(self.fuzzy.listbox.count(), 1)
        self.assertEqual(self.fuzzy.listbox.item(0).text(), "Banana")
    
    def test_no_match(self):
        """Test no matches found."""
        self.fuzzy.entry.setText("XYZ")
        self.fuzzy._update_listbox()
        self.assertEqual(self.fuzzy.listbox.count(), 0)
    
    def test_empty_search(self):
        """Test empty search shows all values."""
        self.fuzzy.entry.setText("")
        self.fuzzy._update_listbox()
        self.assertEqual(self.fuzzy.listbox.count(), len(self.test_values))
        for i, value in enumerate(self.test_values):
            self.assertEqual(self.fuzzy.listbox.item(i).text(), value)
    
    def test_set_values(self):
        """Test setting new values."""
        new_values = ["One", "Two", "Three"]
        self.fuzzy.set_values(new_values)
        self.fuzzy.entry.setText("")
        self.fuzzy._update_listbox()
        self.assertEqual(self.fuzzy.listbox.count(), len(new_values))
        for i, value in enumerate(new_values):
            self.assertEqual(self.fuzzy.listbox.item(i).text(), value)
    
    def test_get_value(self):
        """Test getting current value."""
        test_value = "Test Value"
        self.fuzzy.entry.setText(test_value)
        self.assertEqual(self.fuzzy.get(), test_value)
    
    def test_clear(self):
        """Test clearing the search."""
        self.fuzzy.entry.setText("Test")
        self.fuzzy.clear()
        self.assertEqual(self.fuzzy.get(), "")
        self.assertEqual(self.fuzzy.listbox.count(), len(self.test_values))

if __name__ == '__main__':
    unittest.main()