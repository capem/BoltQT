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
            print(f"[DEBUG] Updating PDF link in Excel: file={file_path}, sheet={sheet_name}, row={row_idx}, column={column_name}")
            print(f"[DEBUG] Linking to PDF: {pdf_path}")
            
            # Load workbook
            wb = load_workbook(file_path)
            ws = wb[sheet_name]
            
            # Find the column index
            header = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
            if column_name not in header:
                raise ValueError(f"Column '{column_name}' not found")
            col_idx = header[column_name]
            
            # Get the cell
            excel_row = row_idx + 2  # +2 for header and 1-based index
            cell = ws.cell(row=excel_row, column=col_idx)
            
            print(f"[DEBUG] Excel cell: {cell.coordinate}, Current value: {cell.value}")
            
            # Store original hyperlink
            original_link = None
            if cell.hyperlink:
                original_link = cell.hyperlink.target if hasattr(cell.hyperlink, 'target') else str(cell.hyperlink)
                print(f"[DEBUG] Found existing hyperlink: {original_link}")
            
            # Check if paths are on different mount points/drives
            excel_drive = os.path.splitdrive(os.path.abspath(file_path))[0]
            pdf_drive = os.path.splitdrive(os.path.abspath(pdf_path))[0]
            
            # For network paths, get the server and share
            excel_mount = excel_drive
            pdf_mount = pdf_drive
            
            # Handle UNC paths (network shares)
            if file_path.startswith('\\\\'):
                excel_parts = file_path.split('\\')
                if len(excel_parts) >= 4:  # \\server\share\...
                    excel_mount = f"\\\\{excel_parts[2]}\\{excel_parts[3]}"
                    
            if pdf_path.startswith('\\\\'):
                pdf_parts = pdf_path.split('\\')
                if len(pdf_parts) >= 4:  # \\server\share\...
                    pdf_mount = f"\\\\{pdf_parts[2]}\\{pdf_parts[3]}"
            
            # Also handle forward slash network paths
            if file_path.startswith('//'):
                excel_parts = file_path.split('/')
                if len(excel_parts) >= 4:  # //server/share/...
                    excel_mount = f"//{excel_parts[2]}/{excel_parts[3]}"
                    
            if pdf_path.startswith('//'):
                pdf_parts = pdf_path.split('/')
                if len(pdf_parts) >= 4:  # //server/share/...
                    pdf_mount = f"//{pdf_parts[2]}/{pdf_parts[3]}"
            
            print(f"[DEBUG] Excel mount: {excel_mount}, PDF mount: {pdf_mount}")
            
            # Determine if we can use a relative path
            use_relative_path = excel_mount == pdf_mount
            
            # Set the target path
            if use_relative_path:
                try:
                    # Use relative path if possible
                    target_path = os.path.relpath(pdf_path, os.path.dirname(file_path))
                    print(f"[DEBUG] Using relative path: {target_path}")
                except ValueError as e:
                    print(f"[DEBUG] Error creating relative path: {str(e)}")
                    target_path = pdf_path
                    print(f"[DEBUG] Falling back to absolute path: {target_path}")
            else:
                # Use absolute path if on different mounts
                target_path = pdf_path
                print(f"[DEBUG] Using absolute path (different mounts): {target_path}")
                print(f"[DEBUG] path is on mount '{pdf_mount}', start on mount '{excel_mount}'")
            
            # Update hyperlink (handle different openpyxl versions)
            try:
                # Method 1: Using Hyperlink class (newer versions of openpyxl)
                from openpyxl.worksheet.hyperlink import Hyperlink
                try:
                    hyperlink = Hyperlink(
                        ref=cell.coordinate,
                        target=target_path
                    )
                    # For compatibility with different versions, try to add target_mode attribute
                    # if it doesn't exist in the constructor
                    hyperlink.target_mode = "file"
                    cell.hyperlink = hyperlink
                    print(f"[DEBUG] Updated hyperlink using newer API: {target_path}")
                except TypeError as e:
                    # Try the older API if the newer one fails
                    print(f"[DEBUG] Newer hyperlink API failed: {str(e)}, trying older API")
                    raise e
            except Exception as e:
                try:
                    # Method 2: Direct assignment (older versions)
                    cell.hyperlink = target_path
                    print(f"[DEBUG] Updated hyperlink using direct assignment: {target_path}")
                except Exception as e2:
                    # Method 3: Last resort - set the display text to the path
                    print(f"[DEBUG] Hyperlink methods failed: {str(e)}, {str(e2)}. Setting display text instead.")
                    cell.value = f"Link: {target_path}"
            
            # Save workbook
            wb.save(file_path)
            print(f"[DEBUG] Excel file saved successfully")
            
            # Update cache
            self._hyperlink_cache[row_idx] = True
            
            return original_link
            
        except Exception as e:
            print(f"[DEBUG] Error updating PDF link: {str(e)}")
            return None
    
    def revert_pdf_link(
        self,
        excel_file: str,
        sheet_name: str,
        row_idx: int,
        filter2_col: str,
        original_hyperlink: Optional[str],
        original_value: str,
    ) -> bool:
        """Revert PDF hyperlink in Excel file.
        
        Args:
            excel_file: Path to the Excel file.
            sheet_name: Name of the sheet.
            row_idx: 0-based row index.
            filter2_col: Name of the filter2 column.
            original_hyperlink: Original hyperlink to restore, or None to remove hyperlink.
            original_value: Original value to restore.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            print(f"[DEBUG] Reverting hyperlink for row {row_idx} in {excel_file}, sheet {sheet_name}")
            print(f"[DEBUG] Original hyperlink: {original_hyperlink}, Original value: {original_value}")
            
            # Load workbook
            from openpyxl import load_workbook
            from openpyxl.worksheet.hyperlink import Hyperlink
            
            wb = load_workbook(excel_file)
            ws = wb[sheet_name]
            
            # Find the column index
            header = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
            if filter2_col not in header:
                raise ValueError(f"Column '{filter2_col}' not found")
            col_idx = header[filter2_col]
            
            # Get the cell
            cell = ws.cell(row=row_idx + 2, column=col_idx)  # +2 for header and 1-based index
            print(f"[DEBUG] Identified Excel cell: {cell.coordinate}, Current value: {cell.value}")
            
            # Update or remove hyperlink - handle different openpyxl versions
            if original_hyperlink:
                try:
                    # Method 1: Using Hyperlink class (newer versions of openpyxl)
                    hyperlink = Hyperlink(
                        ref=cell.coordinate,
                        target=original_hyperlink
                    )
                    # For compatibility with different versions, try to add target_mode after constructor
                    hyperlink.target_mode = "file"
                    cell.hyperlink = hyperlink
                    print(f"[DEBUG] Restored hyperlink using newer API: {original_hyperlink}")
                except TypeError as e:
                    try:
                        # Method 2: Direct assignment (older versions)
                        cell.hyperlink = original_hyperlink
                        print(f"[DEBUG] Restored hyperlink using direct assignment: {original_hyperlink}")
                    except Exception as e2:
                        print(f"[DEBUG] Hyperlink methods failed: {str(e)}, {str(e2)}. Setting display text only.")
                        # Fallback: Set display text only
                        cell.value = f"{original_value} [Link:{original_hyperlink}]"
                        print(f"[DEBUG] Set display text with link reference")
            else:
                # Remove hyperlink - handle different openpyxl versions
                try:
                    cell.hyperlink = None
                    print(f"[DEBUG] Removed hyperlink")
                except Exception as e:
                    # If direct removal fails, try other methods
                    try:
                        # Some versions may use cell._hyperlink
                        if hasattr(cell, '_hyperlink'):
                            cell._hyperlink = None
                            print(f"[DEBUG] Removed hyperlink using _hyperlink attribute")
                    except Exception as e2:
                        print(f"[DEBUG] Failed to remove hyperlink: {str(e)}, {str(e2)}")
            
            # Ensure cell value is restored
            if cell.value != original_value:
                cell.value = original_value
                print(f"[DEBUG] Restored cell value to: {original_value}")
            
            # Save workbook
            wb.save(excel_file)
            print(f"[DEBUG] Excel file saved successfully after reversion")
            
            # Update cache
            self._hyperlink_cache[row_idx] = original_hyperlink is not None
            
            return True
            
        except Exception as e:
            print(f"[DEBUG] Error reverting PDF link: {str(e)}")
            return False

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