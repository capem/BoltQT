import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import tempfile
import shutil
from pathlib import Path
import json
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

from src.utils.config_manager import ConfigManager
from src.utils.excel_manager import ExcelManager
from src.utils.pdf_manager import PDFManager
from src.utils.vision_manager import VisionManager
from src.ui.processing_tab import ProcessingTab


class TestProcessingTabFlow(unittest.TestCase):
    """Test cases for the processing tab workflow."""

    @classmethod
    def setUpClass(cls):
        """Create the application for Qt tests."""
        cls.app = QApplication([])

        # Define test data paths
        cls.test_data_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "data")))
        cls.source_dir = cls.test_data_dir / "Source" / "FA"
        cls.dest_dir = cls.test_data_dir / "Dest"
        cls.excel_file = cls.test_data_dir / "SUIVI OV CHQ OPCVM BC 2023 test.xlsx"

        # Make a backup of the Excel file
        cls.excel_backup = cls.test_data_dir / "SUIVI OV CHQ OPCVM BC 2023 test.backup.xlsx"
        if cls.excel_file.exists():
            shutil.copy2(cls.excel_file, cls.excel_backup)

        # Ensure test directories exist
        cls.source_dir.mkdir(parents=True, exist_ok=True)
        cls.dest_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up the application."""
        # Restore Excel file from backup if it exists
        if cls.excel_backup.exists():
            shutil.copy2(cls.excel_backup, cls.excel_file)
            cls.excel_backup.unlink()

        cls.app.quit()

    def setUp(self):
        """Set up each test."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Create test config file
        self.config_path = self.temp_path / "test_config.json"
        self.test_config = {
            "document_type": "FA",
            "source_folder": str(self.source_dir),
            "excel_file": str(self.excel_file),
            "excel_sheet": "FACTURE",
            "processed_folder": str(self.dest_dir),
            "output_template": "{processed_folder}/{filter3|date.year}/MOIS {filter3|date.month}/{filter2|str.first_word} {filter1} {filter2|str.split_no_last}.pdf",
            "filter1_column": "FOURNISSEUR",
            "filter2_column": "N° FACTURE",
            "filter3_column": "DATE FACTURE",
            "filter4_column": "MONTANT",
            "vision": {
                "enabled": False
            }
        }

        # Write test config
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)

        # Create test PDF file
        self.test_pdf_path = self.source_dir / "TEST_INVOICE.pdf"
        if not self.test_pdf_path.exists():
            # Create a simple PDF file for testing
            with open(self.test_pdf_path, 'wb') as f:
                f.write(b'%PDF-1.4\n%Test PDF file for processing workflow test')

        # Initialize managers
        self.config_manager = ConfigManager()
        self.config_manager._config_file = str(self.config_path)
        self.config_manager.load_config()

        self.excel_manager = ExcelManager()
        self.pdf_manager = PDFManager()
        self.vision_manager = VisionManager(self.config_manager)

        # Mock error and status handlers
        self.error_handler = MagicMock()
        self.status_handler = MagicMock()

        # Initialize processing tab
        self.processing_tab = ProcessingTab(
            config_manager=self.config_manager,
            excel_manager=self.excel_manager,
            pdf_manager=self.pdf_manager,
            vision_manager=self.vision_manager,
            error_handler=self.error_handler,
            status_handler=self.status_handler
        )

    def tearDown(self):
        """Clean up after each test."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Remove test PDF if it exists
        if self.test_pdf_path.exists():
            try:
                self.test_pdf_path.unlink()
            except Exception as e:
                print(f"Warning: Could not remove test PDF: {str(e)}")

        # Clean up any created files in destination directory
        for year_dir in ["2023", "2024", "2025"]:
            year_path = self.dest_dir / year_dir
            if year_path.exists():
                for month_dir in year_path.glob("MOIS *"):
                    for pdf_file in month_dir.glob("*TEST*.pdf"):
                        try:
                            pdf_file.unlink()
                        except Exception as e:
                            print(f"Warning: Could not remove test file {pdf_file}: {str(e)}")

    def test_filter_creation(self):
        """Test that filters are created correctly based on configuration."""
        # Verify that the correct number of filters were created
        self.assertEqual(len(self.processing_tab.filter_frames), 4,
                         "Should have created 4 filters based on configuration")

        # Verify filter labels match configuration
        self.assertEqual(self.processing_tab.filter_frames[0]["column"], "FOURNISSEUR")
        self.assertEqual(self.processing_tab.filter_frames[1]["column"], "N° FACTURE")
        self.assertEqual(self.processing_tab.filter_frames[2]["column"], "DATE FACTURE")
        self.assertEqual(self.processing_tab.filter_frames[3]["column"], "MONTANT")

        # Verify that each filter has a fuzzy search component
        for filter_frame in self.processing_tab.filter_frames:
            self.assertIsNotNone(filter_frame["fuzzy"], "Each filter should have a fuzzy search component")

    def test_filter_population(self):
        """Test that filters are populated with values from Excel."""
        # Force reload of Excel data
        self.excel_manager.load_excel_data(str(self.excel_file), "FACTURE", force_reload=True)

        # Manually trigger filter population
        self.processing_tab._load_filter_values(0)

        # Process events to ensure UI updates
        QApplication.processEvents()

        # Verify that the first filter has values
        filter1_values = self.processing_tab.filter_frames[0]["fuzzy"].all_values
        self.assertGreater(len(filter1_values), 0, "Filter 1 should have values from Excel")

        # Select a value in the first filter
        if filter1_values:
            test_supplier = filter1_values[0]
            self.processing_tab.filter_frames[0]["fuzzy"].set(test_supplier)
            self.processing_tab._on_filter_selected(0)

            # Process events to ensure UI updates
            QApplication.processEvents()

            # Verify that the second filter has values
            filter2_values = self.processing_tab.filter_frames[1]["fuzzy"].all_values
            self.assertGreater(len(filter2_values), 0,
                              f"Filter 2 should have values after selecting '{test_supplier}' in Filter 1")

    def test_filter2_special_formatting(self):
        """Test that filter2 values are formatted with row numbers and checkmarks."""
        # Force reload of Excel data
        self.excel_manager.load_excel_data(str(self.excel_file), "FACTURE", force_reload=True)

        # Get a sample row from Excel
        df = self.excel_manager.excel_data
        if len(df) > 0:
            # Get the first row
            row_idx = 0
            filter2_value = str(df.iloc[row_idx][self.test_config["filter2_column"]])

            # Format the filter2 value
            formatted_value = self.processing_tab._format_filter2_value(filter2_value, row_idx)

            # Verify that the formatted value contains the row number
            self.assertIn(f"⟨Excel Row: {row_idx + 2}⟩", formatted_value,
                         "Formatted filter2 value should contain Excel row number")

            # Parse the formatted value
            parsed_value, parsed_row_idx = self.processing_tab._parse_filter2_value(formatted_value)

            # Verify that parsing works correctly
            self.assertEqual(parsed_value, filter2_value,
                            "Parsed value should match original value")
            self.assertEqual(parsed_row_idx, row_idx,
                            "Parsed row index should match original row index")

    def test_filter_cascade(self):
        """Test that selecting a value in one filter updates subsequent filters."""
        # Force reload of Excel data
        self.excel_manager.load_excel_data(str(self.excel_file), "FACTURE", force_reload=True)

        # Manually trigger filter population
        self.processing_tab._load_filter_values(0)

        # Process events to ensure UI updates
        QApplication.processEvents()

        # Get values for the first filter
        filter1_values = self.processing_tab.filter_frames[0]["fuzzy"].all_values

        if len(filter1_values) > 0:
            # Select a value in the first filter
            test_supplier = filter1_values[0]
            self.processing_tab.filter_frames[0]["fuzzy"].set(test_supplier)

            # Manually trigger filter selection
            self.processing_tab._on_filter_selected(0)

            # Process events to ensure UI updates
            QApplication.processEvents()

            # Verify that the second filter has values
            filter2_values = self.processing_tab.filter_frames[1]["fuzzy"].all_values
            self.assertGreater(len(filter2_values), 0,
                              f"Filter 2 should have values after selecting '{test_supplier}' in Filter 1")

            if len(filter2_values) > 0:
                # Select a value in the second filter
                test_invoice = filter2_values[0]
                self.processing_tab.filter_frames[1]["fuzzy"].set(test_invoice)

                # Manually trigger filter selection
                self.processing_tab._on_filter_selected(1)

                # Process events to ensure UI updates
                QApplication.processEvents()

                # Verify that the third filter has values
                filter3_values = self.processing_tab.filter_frames[2]["fuzzy"].all_values
                self.assertGreater(len(filter3_values), 0,
                                  f"Filter 3 should have values after selecting '{test_invoice}' in Filter 2")

    def test_vision_result_propagation(self):
        """Test that vision results are properly propagated to filters."""
        # Enable vision in config
        config = self.config_manager.get_config()
        config["vision"]["enabled"] = True

        # Create vision result data
        vision_result = {
            "normalized_data": {
                "filter1": "TEST COMPANY",
                "filter2": "INV-12345",
                "filter3": "15/04/2025",
                "filter4": "1000.00"
            }
        }

        # Set the current PDF path
        self.processing_tab.current_pdf = str(self.test_pdf_path)

        # Call the vision result handler directly
        self.processing_tab._apply_vision_result(vision_result)

        # Process events to ensure UI updates
        QApplication.processEvents()

        # Verify that filters were populated with vision results
        self.assertEqual(self.processing_tab.filter_frames[0]["fuzzy"].get(), "TEST COMPANY")
        self.assertEqual(self.processing_tab.filter_frames[2]["fuzzy"].get(), "15/04/2025")
        self.assertEqual(self.processing_tab.filter_frames[3]["fuzzy"].get(), "1000.00")

        # Note: Filter2 might not match exactly due to fuzzy matching, so we check if it contains the value
        self.assertIn("INV-12345", self.processing_tab.filter_frames[1]["fuzzy"].get())

    def test_process_button_state(self):
        """Test that the process button state is updated correctly based on filter values."""
        # Initially, the process button should be disabled
        self.assertFalse(self.processing_tab.process_button.isEnabled(),
                        "Process button should be disabled initially")

        # Set values for all filters
        for i, filter_frame in enumerate(self.processing_tab.filter_frames):
            filter_frame["fuzzy"].set(f"Test Value {i+1}")

        # Manually update process button state
        self.processing_tab._update_process_button()

        # Process events to ensure UI updates
        QApplication.processEvents()

        # Verify that the process button is enabled
        self.assertTrue(self.processing_tab.process_button.isEnabled(),
                       "Process button should be enabled when all filters have values")

        # Clear one filter
        self.processing_tab.filter_frames[0]["fuzzy"].clear()

        # Manually update process button state
        self.processing_tab._update_process_button()

        # Process events to ensure UI updates
        QApplication.processEvents()

        # Verify that the process button is disabled
        self.assertFalse(self.processing_tab.process_button.isEnabled(),
                        "Process button should be disabled when any filter is empty")

if __name__ == '__main__':
    unittest.main()
