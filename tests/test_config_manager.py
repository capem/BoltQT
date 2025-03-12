import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import json
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from src.utils.config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Create the application for Qt tests."""
        cls.app = QApplication([])
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the application."""
        cls.app.quit()
    
    def setUp(self):
        """Set up each test."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        
        # Create ConfigManager instance
        self.config_manager = ConfigManager()
        # Override config file path
        self.config_manager._config_file = str(self.config_path)
    
    def tearDown(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()
    
    def test_default_config(self):
        """Test default configuration values."""
        config = self.config_manager.get_config()
        self.assertEqual(config["source_folder"], "")
        self.assertEqual(config["excel_file"], "")
        self.assertEqual(config["excel_sheet"], "")
        self.assertEqual(config["processed_folder"], "")
        self.assertEqual(config["output_template"], "")
        self.assertEqual(config["filter1_column"], "")
        self.assertEqual(config["filter2_column"], "")
        self.assertEqual(config["filter3_column"], "")
        self.assertEqual(config["filter4_column"], "")
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        test_config = {
            "source_folder": "/test/source",
            "excel_file": "/test/excel.xlsx",
            "excel_sheet": "Sheet1",
            "processed_folder": "/test/processed",
            "output_template": "${filter1}/${filter2}.pdf",
            "filter1_column": "Column1",
            "filter2_column": "Column2",
        }
        
        # Update config
        self.config_manager.update_config(test_config)
        
        # Create new ConfigManager to test loading
        new_manager = ConfigManager()
        new_manager._config_file = str(self.config_path)
        
        # Load config
        new_manager.load_config()
        loaded_config = new_manager.get_config()
        
        # Check values
        for key, value in test_config.items():
            self.assertEqual(loaded_config[key], value)
    
    def test_invalid_config_file(self):
        """Test handling of invalid config file."""
        # Write invalid JSON
        with open(self.config_path, 'w') as f:
            f.write("invalid json")
        
        # Create new ConfigManager
        manager = ConfigManager()
        manager._config_file = str(self.config_path)
        
        # Load config should not raise exception and use defaults
        manager.load_config()
        config = manager.get_config()
        self.assertEqual(config["source_folder"], "")
    
    def test_partial_config_update(self):
        """Test updating only some config values."""
        initial_config = self.config_manager.get_config()
        update = {"source_folder": "/new/source"}
        
        self.config_manager.update_config(update)
        new_config = self.config_manager.get_config()
        
        # Check updated value
        self.assertEqual(new_config["source_folder"], "/new/source")
        
        # Check other values remain unchanged
        for key in initial_config:
            if key != "source_folder":
                self.assertEqual(initial_config[key], new_config[key])
    
    def test_config_change_callback(self):
        """Test configuration change callback."""
        callback_called = False
        
        def callback():
            nonlocal callback_called
            callback_called = True
        
        # Add callback
        self.config_manager.add_change_callback(callback)
        
        # Update config
        self.config_manager.update_config({"source_folder": "/test"})
        
        # Check callback was called
        self.assertTrue(callback_called)
    
    def test_remove_callback(self):
        """Test removing configuration change callback."""
        callback_called = False
        
        def callback():
            nonlocal callback_called
            callback_called = True
        
        # Add and remove callback
        self.config_manager.add_change_callback(callback)
        self.config_manager.remove_change_callback(callback)
        
        # Update config
        self.config_manager.update_config({"source_folder": "/test"})
        
        # Check callback was not called
        self.assertFalse(callback_called)
    
    def test_clear_callbacks(self):
        """Test clearing all configuration change callbacks."""
        callback_called = False
        
        def callback():
            nonlocal callback_called
            callback_called = True
        
        # Add callback and clear all
        self.config_manager.add_change_callback(callback)
        self.config_manager.clear_callbacks()
        
        # Update config
        self.config_manager.update_config({"source_folder": "/test"})
        
        # Check callback was not called
        self.assertFalse(callback_called)
    
    def test_signal_emission(self):
        """Test that config_changed signal is emitted."""
        signal_received = False
        
        def slot():
            nonlocal signal_received
            signal_received = True
        
        # Connect to signal
        self.config_manager.config_changed.connect(slot)
        
        # Update config
        self.config_manager.update_config({"source_folder": "/test"})
        
        # Check signal was received
        self.assertTrue(signal_received)

if __name__ == '__main__':
    unittest.main()