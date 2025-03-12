from __future__ import annotations
from typing import Dict, Optional, Tuple, List, Any
from datetime import datetime
import os
import pandas as pd
from openpyxl import load_workbook
from PyQt6.QtCore import QObject
class ExcelManager(QObject):
    """Manages Excel file operations and data caching."""
    
    def __init__(self) -> None:
        super().__init__()
        self.excel_data: Optional[pd.DataFrame] = None
        self._hyperlink_cache: Dict[int, bool] = {}
        self._last_cached_key: Optional[str] = None
        self._last_file: Optional[str] = None
        self._last_sheet: Optional[str] = None
        self._sheet_cache: Dict[str, list] = {}  # Cache for sheet names
        self._column_cache: Dict[str, list] = {}  # Cache for column names

    def clear_caches(self) -> None:
        """Clear all cached data."""
        self._hyperlink_cache.clear()
        self._last_cached_key = None
        self._last_file = None
        self._last_sheet = None
        self._sheet_cache.clear()
        self._column_cache.clear()
        self.excel_data = None
        print("[DEBUG] All caches cleared")
        self._last_sheet: Optional[str] = None
    
    def load_excel_data(self, file_path: str, sheet_name: str) -> bool:
        """Load Excel data from file into DataFrame.
        
        Returns:
            bool: True if data was reloaded, False if using cached data
        """
        if not file_path or not sheet_name:
            return False
            
        try:
            # Check if we need to reload
            if (self.excel_data is not None and 
                self._last_file == file_path and 
                self._last_sheet == sheet_name):
                return False
            
            print(f"[DEBUG] Loading Excel data from {file_path}, sheet: {sheet_name}")
            
            # Load the data
            self.excel_data = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                engine="openpyxl"
            )
            
            # Update last loaded file info
            self._last_file = file_path
            self._last_sheet = sheet_name
            
            # Clear hyperlink cache
            self._hyperlink_cache.clear()
            self._last_cached_key = None
            
            return True
            
        except Exception as e:
            print(f"[DEBUG] Error loading Excel data: {str(e)}")
            self.excel_data = None
            self._last_file = None
            self._last_sheet = None
            self._hyperlink_cache.clear()
            self._last_cached_key = None
            raise
    
    def cache_hyperlinks_for_column(
        self, file_path: str, sheet_name: str, column_name: str
    ) -> None:
        """Cache hyperlinks for a specific column."""
        try:
            cache_key = f"{file_path}:{sheet_name}:{column_name}"
            
            # Check if we need to update cache
            if (self._last_cached_key == cache_key and self._hyperlink_cache):
                print("[DEBUG] Using existing hyperlink cache")
                return
            
            print(f"[DEBUG] Caching hyperlinks for column: {column_name}")
            
            # Load workbook
            wb = load_workbook(file_path, data_only=True)
            ws = wb[sheet_name]
            
            # Find the column index
            header = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
            if column_name not in header:
                print(f"[DEBUG] Column '{column_name}' not found")
                return
            col_idx = header[column_name]
            
            # Clear existing cache
            self._hyperlink_cache.clear()
            
            # Cache hyperlinks
            for row_idx in range(2, ws.max_row + 1):  # Skip header row
                cell = ws.cell(row=row_idx, column=col_idx)
                self._hyperlink_cache[row_idx - 2] = cell.hyperlink is not None
            
            self._last_cached_key = cache_key
            
        except Exception as e:
            print(f"[DEBUG] Error caching hyperlinks: {str(e)}")
            self._hyperlink_cache.clear()
            self._last_cached_key = None
            raise
    
    def has_hyperlink(self, row_idx: int) -> bool:
        """Check if a specific row has a hyperlink."""
        return bool(self._hyperlink_cache.get(row_idx, False))
    
    def update_pdf_link(
        self,
        file_path: str,
        sheet_name: str,
        row_idx: int,
        pdf_path: str,
        column_name: str,
    ) -> Optional[str]:
        """Update PDF hyperlink in Excel file.
        
        Returns:
            Optional[str]: Original hyperlink if there was one, None otherwise
        """
        try:
            # Load workbook
            wb = load_workbook(file_path)
            ws = wb[sheet_name]
            
            # Find the column index
            header = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
            if column_name not in header:
                raise ValueError(f"Column '{column_name}' not found")
            col_idx = header[column_name]
            
            # Get the cell
            cell = ws.cell(row=row_idx + 2, column=col_idx)  # +2 for header and 1-based index
            
            # Store original hyperlink
            original_link = None
            if cell.hyperlink:
                original_link = cell.hyperlink.target
            
            # Update hyperlink
            from openpyxl.worksheet.hyperlink import Hyperlink
            cell.hyperlink = Hyperlink(
                ref=cell.coordinate,
                target=os.path.relpath(pdf_path, os.path.dirname(file_path)),
                target_mode="file"
            )
            
            # Save workbook
            wb.save(file_path)
            
            # Update cache
            self._hyperlink_cache[row_idx] = True
            
            return original_link
            
        except Exception as e:
            print(f"[DEBUG] Error updating PDF link: {str(e)}")
            raise
    
    def revert_pdf_link(
        self,
        file_path: str,
        sheet_name: str,
        row_idx: int,
        original_link: Optional[str],
        column_name: str,
    ) -> None:
        """Revert PDF hyperlink to its original state."""
        try:
            # Load workbook
            wb = load_workbook(file_path)
            ws = wb[sheet_name]
            
            # Find the column index
            header = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
            if column_name not in header:
                raise ValueError(f"Column '{column_name}' not found")
            col_idx = header[column_name]
            
            # Get the cell
            cell = ws.cell(row=row_idx + 2, column=col_idx)  # +2 for header and 1-based index
            
            # Revert hyperlink
            if original_link:
                from openpyxl.worksheet.hyperlink import Hyperlink
                cell.hyperlink = Hyperlink(
                    ref=cell.coordinate,
                    target=original_link,
                    target_mode="file"
                )
            else:
                cell.hyperlink = None
            
            # Save workbook
            wb.save(file_path)
            
            # Update cache
            self._hyperlink_cache[row_idx] = bool(original_link)
            
        except Exception as e:
            print(f"[DEBUG] Error reverting PDF link: {str(e)}")
            raise

    def get_available_sheets(self, file_path: str) -> list[str]:
        """Get list of available sheets in Excel file.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            List of sheet names
        """
        try:
            # Check cache first
            if file_path in self._sheet_cache:
                return self._sheet_cache[file_path]
            
            # Load workbook
            wb = load_workbook(file_path, read_only=True)
            sheet_names = wb.sheetnames
            
            # Cache results
            self._sheet_cache[file_path] = sheet_names
            
            return sheet_names
            
        except Exception as e:
            print(f"[DEBUG] Error getting sheet names: {str(e)}")
            raise
            
    def get_sheet_columns(self, file_path: str, sheet_name: str) -> list[str]:
        """Get list of column names from specified sheet.
        
        Args:
            file_path: Path to Excel file
            sheet_name: Name of sheet to read
            
        Returns:
            List of column names from first row
        """
        try:
            # Generate cache key
            cache_key = f"{file_path}:{sheet_name}"
            
            # Check cache first
            if cache_key in self._column_cache:
                return self._column_cache[cache_key]
            
            # Load workbook and get first row only
            wb = load_workbook(file_path, read_only=True)
            ws = wb[sheet_name]
            
            # Get header row values
            header_row = next(ws.rows)
            column_names = [cell.value for cell in header_row if cell.value]
            
            # Cache results
            self._column_cache[cache_key] = column_names
            
            return column_names
            
        except Exception as e:
            print(f"[DEBUG] Error getting column names: {str(e)}")
            raise
    
    def add_new_row(
        self,
        file_path: str,
        sheet_name: str,
        columns: List[str],
        values: List[str],
    ) -> Tuple[Dict[str, Any], int]:
        """Add a new row to the Excel file.
        
        Returns:
            Tuple[Dict[str, Any], int]: Dictionary of row data and the row index
        """
        try:
            # Load workbook
            wb = load_workbook(file_path)
            ws = wb[sheet_name]
            
            # Find column indices
            header = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
            col_indices = []
            for col in columns:
                if col not in header:
                    raise ValueError(f"Column '{col}' not found")
                col_indices.append(header[col])
            
            # Add new row
            new_row = ws.max_row + 1
            for col_idx, value in zip(col_indices, values):
                cell = ws.cell(row=new_row, column=col_idx)
                cell.value = value
            
            # Save workbook
            wb.save(file_path)
            
            # Reload Excel data
            self.load_excel_data(file_path, sheet_name)
            
            # Get row data
            row_idx = new_row - 2  # Convert to 0-based index
            row_data = self.excel_data.iloc[row_idx].to_dict()
            
            return row_data, row_idx
            
        except Exception as e:
            print(f"[DEBUG] Error adding new row: {str(e)}")
            raise