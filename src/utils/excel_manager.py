from __future__ import annotations
from typing import Dict, Optional, Tuple, List, Any
import os
import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.hyperlink import Hyperlink
from PyQt6.QtCore import QObject
from shutil import copy2
from os import path, remove
import traceback


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

    def load_excel_data(
        self, file_path: str, sheet_name: str, force_reload: bool = False
    ) -> bool:
        """Load Excel data from file into DataFrame.

        Args:
            file_path: Path to the Excel file
            sheet_name: Name of the sheet to load
            force_reload: If True, will reload data even if it's already cached

        Returns:
            bool: True if data was reloaded, False if using cached data
        """
        if not file_path or not sheet_name:
            return False

        try:
            # Check if we need to reload
            if (
                not force_reload
                and self.excel_data is not None
                and self._last_file == file_path
                and self._last_sheet == sheet_name
            ):
                print(f"[DEBUG] Using cached Excel data (force_reload={force_reload})")
                return False

            print(f"[DEBUG] Loading Excel data from {file_path}, sheet: {sheet_name}")

            # Try to normalize path for network paths
            normalized_path = file_path
            # Handle Windows UNC paths
            if file_path.startswith("//") or file_path.startswith("\\\\"):
                try:
                    # Make sure the path is in a consistent format
                    parts = file_path.replace("/", "\\").strip("\\").split("\\")
                    if len(parts) >= 2:
                        normalized_path = f"\\\\{parts[0]}\\{parts[1]}"
                        if len(parts) > 2:
                            normalized_path += "\\" + "\\".join(parts[2:])
                    print(f"[DEBUG] Normalized network path: {normalized_path}")
                except Exception as path_err:
                    print(f"[DEBUG] Path normalization error: {str(path_err)}")

            # Load the data
            try:
                self.excel_data = pd.read_excel(
                    normalized_path, sheet_name=sheet_name, engine="openpyxl"
                )
            except OSError:
                print(
                    f"[DEBUG] Failed to read with normalized path, trying original path"
                )
                # If normalized path fails, try the original path
                self.excel_data = pd.read_excel(
                    file_path, sheet_name=sheet_name, engine="openpyxl"
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
            if self._last_cached_key == cache_key and self._hyperlink_cache:
                print("[DEBUG] Using existing hyperlink cache")
                return

            print(f"[DEBUG] Caching hyperlinks for column: {column_name}")

            # Try to normalize path for network paths
            normalized_path = file_path
            # Handle Windows UNC paths
            if file_path.startswith("//") or file_path.startswith("\\\\"):
                try:
                    # Make sure the path is in a consistent format
                    parts = file_path.replace("/", "\\").strip("\\").split("\\")
                    if len(parts) >= 2:
                        normalized_path = f"\\\\{parts[0]}\\{parts[1]}"
                        if len(parts) > 2:
                            normalized_path += "\\" + "\\".join(parts[2:])
                    print(f"[DEBUG] Normalized network path: {normalized_path}")
                except Exception as path_err:
                    print(f"[DEBUG] Path normalization error: {str(path_err)}")

            try:
                # Load workbook
                wb = load_workbook(normalized_path, data_only=True)
            except:
                print(
                    f"[DEBUG] Failed to load workbook with normalized path, trying original path"
                )
                try:
                    wb = load_workbook(file_path, data_only=True)
                except Exception as wb_err:
                    print(f"[DEBUG] Could not load workbook: {str(wb_err)}")
                    # If we can't load the workbook, just return without error
                    self._hyperlink_cache.clear()
                    return

            try:
                ws = wb[sheet_name]
            except KeyError as key_err:
                print(f"[DEBUG] Sheet '{sheet_name}' not found: {str(key_err)}")
                return
            except Exception as sheet_err:
                print(f"[DEBUG] Error accessing sheet: {str(sheet_err)}")
                return

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
                try:
                    cell = ws.cell(row=row_idx, column=col_idx)
                    self._hyperlink_cache[row_idx - 2] = cell.hyperlink is not None
                except Exception as cell_err:
                    print(
                        f"[DEBUG] Error reading cell at row {row_idx}: {str(cell_err)}"
                    )
                    # Continue with next cell instead of aborting

            self._last_cached_key = cache_key

        except Exception as e:
            print(f"[DEBUG] Error caching hyperlinks: {str(e)}")
            self._hyperlink_cache.clear()
            self._last_cached_key = None
            # Don't raise, just silently fail

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
            print(
                f"[DEBUG] Updating PDF link in Excel: file={file_path}, sheet={sheet_name}, row={row_idx}, column={column_name}"
            )
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
                original_link = (
                    cell.hyperlink.target
                    if hasattr(cell.hyperlink, "target")
                    else str(cell.hyperlink)
                )
                print(f"[DEBUG] Found existing hyperlink: {original_link}")

            # Check if paths are on different mount points/drives
            excel_drive = os.path.splitdrive(os.path.abspath(file_path))[0]
            pdf_drive = os.path.splitdrive(os.path.abspath(pdf_path))[0]

            # For network paths, get the server and share
            excel_mount = excel_drive
            pdf_mount = pdf_drive

            # Handle UNC paths (network shares)
            if file_path.startswith("\\\\"):
                excel_parts = file_path.split("\\")
                if len(excel_parts) >= 4:  # \\server\share\...
                    excel_mount = f"\\\\{excel_parts[2]}\\{excel_parts[3]}"

            if pdf_path.startswith("\\\\"):
                pdf_parts = pdf_path.split("\\")
                if len(pdf_parts) >= 4:  # \\server\share\...
                    pdf_mount = f"\\\\{pdf_parts[2]}\\{pdf_parts[3]}"

            # Also handle forward slash network paths
            if file_path.startswith("//"):
                excel_parts = file_path.split("/")
                if len(excel_parts) >= 4:  # //server/share/...
                    excel_mount = f"//{excel_parts[2]}/{excel_parts[3]}"

            if pdf_path.startswith("//"):
                pdf_parts = pdf_path.split("/")
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
                print(
                    f"[DEBUG] path is on mount '{pdf_mount}', start on mount '{excel_mount}'"
                )

            # Update hyperlink using Excel formula and styling

            # Extract original value or use existing cell value
            hyperlink = Hyperlink(ref=cell.coordinate, target=target_path)

            hyperlink.target_mode = "file"
            cell.hyperlink = hyperlink
            cell.style = "Hyperlink"

            # Save workbook
            wb.save(file_path)
            print(f"[DEBUG] Set HYPERLINK formula: {cell.value}")
            print("[DEBUG] Excel file saved successfully")

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
            print(
                f"[DEBUG] Reverting hyperlink for row {row_idx} in {excel_file}, sheet {sheet_name}"
            )
            print(
                f"[DEBUG] Original hyperlink: {original_hyperlink}, Original value: {original_value}"
            )

            wb = load_workbook(excel_file)
            ws = wb[sheet_name]

            # Find the column index
            header = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
            if filter2_col not in header:
                raise ValueError(f"Column '{filter2_col}' not found")
            col_idx = header[filter2_col]

            # Get the cell
            cell = ws.cell(
                row=row_idx + 2, column=col_idx
            )  # +2 for header and 1-based index
            print(
                f"[DEBUG] Identified Excel cell: {cell.coordinate}, Current value: {cell.value}"
            )

            # Update or remove hyperlink - handle different openpyxl versions
            if original_hyperlink:
                try:
                    # Method 1: Using Hyperlink class (newer versions of openpyxl)
                    hyperlink = Hyperlink(
                        ref=cell.coordinate, target=original_hyperlink
                    )
                    # For compatibility with different versions, try to add target_mode after constructor
                    hyperlink.target_mode = "file"
                    cell.hyperlink = hyperlink
                    print(
                        f"[DEBUG] Restored hyperlink using newer API: {original_hyperlink}"
                    )
                except TypeError as e:
                    try:
                        # Method 2: Direct assignment (older versions)
                        cell.hyperlink = original_hyperlink
                        print(
                            f"[DEBUG] Restored hyperlink using direct assignment: {original_hyperlink}"
                        )
                    except Exception as e2:
                        print(
                            f"[DEBUG] Hyperlink methods failed: {str(e)}, {str(e2)}. Setting display text only."
                        )
                        # Fallback: Set display text only
                        cell.value = f"{original_value} [Link:{original_hyperlink}]"
                        print("[DEBUG] Set display text with link reference")
            else:
                # Remove hyperlink - handle different openpyxl versions
                try:
                    cell.hyperlink = None
                    print("[DEBUG] Removed hyperlink")
                except Exception as e:
                    # If direct removal fails, try other methods
                    try:
                        # Some versions may use cell._hyperlink
                        if hasattr(cell, "_hyperlink"):
                            cell._hyperlink = None
                            print(
                                "[DEBUG] Removed hyperlink using _hyperlink attribute"
                            )
                    except Exception as e2:
                        print(
                            f"[DEBUG] Failed to remove hyperlink: {str(e)}, {str(e2)}"
                        )

            # Ensure cell value is restored
            if cell.value != original_value:
                cell.value = original_value
                print(f"[DEBUG] Restored cell value to: {original_value}")

            # Save workbook
            wb.save(excel_file)
            print("[DEBUG] Excel file saved successfully after reversion")

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
            print(
                f"[DEBUG] Cache state before adding new row - size: {len(self._hyperlink_cache)}"
            )

            # Validate input
            if len(columns) != len(values):
                raise ValueError(
                    f"Number of columns ({len(columns)}) and values ({len(values)}) must match"
                )

            print(f"[DEBUG] Adding new row with values: {dict(zip(columns, values))}")

            # Create a backup
            backup_file = file_path + ".bak"
            copy2(file_path, backup_file)
            print(f"[DEBUG] Created backup at {backup_file}")

            try:
                # Load workbook
                wb = load_workbook(file_path)
                ws = wb[sheet_name]

                # Get header row
                header_row = ws[1]
                col_indices = {
                    cell.value: idx + 1 for idx, cell in enumerate(header_row)
                }

                # Verify all filter columns exist
                for col in columns:
                    if col not in col_indices:
                        raise ValueError(
                            f"Column '{col}' not found in Excel file. Available columns: {', '.join(col_indices.keys())}"
                        )

                # Find the first table's range to determine where to add the new row
                table_end_row = None
                for table in ws.tables.values():
                    try:
                        current_ref = table.ref
                        ref_parts = current_ref.split(":")
                        if len(ref_parts) == 2:
                            end_ref = ref_parts[1]
                            table_end_row = int("".join(filter(str.isdigit, end_ref)))
                            print(f"[DEBUG] Found table with end row: {table_end_row}")
                            break  # Use the first table found
                    except Exception as e:
                        print(f"[DEBUG] Error processing table reference: {str(e)}")
                        continue

                # If we found a table, add the row immediately after it
                if table_end_row:
                    new_row = table_end_row + 1
                else:
                    # Fallback to adding at the end if no table found
                    new_row = ws.max_row + 1

                print(
                    f"[DEBUG] Adding row at index {new_row - 2} (Excel row {new_row})"
                )

                # First pass: Copy all formats from the template row (use row before new row)
                template_row = new_row - 1
                print(f"[DEBUG] Using template row {template_row} for formatting")

                # Second pass: Set values with proper type conversion
                for col, val in zip(columns, values):
                    col_idx = col_indices[col]
                    template_cell = ws.cell(row=template_row, column=col_idx)
                    new_cell = ws.cell(row=new_row, column=col_idx)

                    # Convert value based on the column type
                    if "DATE" in col.upper() and val:
                        try:
                            # Try to parse date in various formats
                            date_formats = [
                                "%d/%m/%Y",
                                "%d-%m-%Y",
                                "%Y-%m-%d",
                                "%Y/%m/%d",
                            ]
                            date_val = None

                            for fmt in date_formats:
                                try:
                                    from datetime import datetime

                                    date_val = datetime.strptime(val, fmt)
                                    break
                                except ValueError:
                                    continue

                            if date_val:
                                new_cell.value = date_val
                                new_cell.number_format = "DD/MM/YYYY"
                            else:
                                # Fallback to pandas datetime parsing
                                date_val = pd.to_datetime(val)
                                new_cell.value = date_val.to_pydatetime()
                                new_cell.number_format = "DD/MM/YYYY"
                        except Exception as e:
                            print(
                                f"[DEBUG] Could not parse date '{val}' for column '{col}': {str(e)}"
                            )
                            new_cell.value = val
                    elif "MNT" in col.upper() or "MONTANT" in col.upper():
                        try:
                            # Handle number format
                            num_str = val.replace(" ", "").replace(",", ".")
                            num_val = float(num_str)
                            new_cell.value = num_val
                            new_cell.number_format = '_-* #,##0.00\\ _€_-;\\-* #,##0.00\\ _€_-;_-* "-"??\\ _€_-;_-@_-'
                            new_cell.style = "Comma"
                        except Exception as e:
                            new_cell.value = val
                            print(
                                f"[DEBUG] Could not parse number '{val}' for column '{col}': {str(e)}"
                            )
                    else:
                        new_cell.value = val

                    print(f"[DEBUG] Set value '{val}' for column '{col}'")

                # Check and expand table ranges to include the new row
                if table_end_row:
                    print("[DEBUG] Checking for tables that need to be expanded")
                    for table in ws.tables.values():
                        try:
                            current_ref = table.ref
                            # Split table reference into components (e.g., 'A1:D10' -> ['A1', 'D10'])
                            ref_parts = current_ref.split(":")
                            if len(ref_parts) != 2:
                                continue

                            start_ref, end_ref = ref_parts

                            # Extract row numbers from references
                            start_row = int("".join(filter(str.isdigit, start_ref)))
                            end_row = int("".join(filter(str.isdigit, end_ref)))

                            # Check if new row is immediately after table
                            if end_row == new_row - 1:
                                # Get column letters from references (e.g., 'A' from 'A1')
                                start_col = "".join(filter(str.isalpha, start_ref))
                                end_col = "".join(filter(str.isalpha, end_ref))

                                # Create new reference that includes the new row
                                new_ref = f"{start_col}{start_row}:{end_col}{new_row}"
                                table.ref = new_ref
                                print(
                                    f"[DEBUG] Expanded table '{table.displayName}' range to {new_ref}"
                                )
                        except Exception as table_e:
                            print(f"[DEBUG] Error expanding table: {str(table_e)}")
                            # Continue with other tables even if one fails
                            continue

                # Save workbook
                wb.save(file_path)

                # Update cache for the new row
                self._hyperlink_cache[new_row - 2] = False

                # Create a row data dictionary that includes all the values
                row_data = {}
                if self.excel_data is not None:
                    # Create data for all columns (initialize with None)
                    for col in self.excel_data.columns:
                        row_data[col] = None

                    # Update with the values we have
                    for col, val in zip(columns, values):
                        row_data[col] = val

                    # Add the new row to our DataFrame
                    self.excel_data = pd.concat(
                        [self.excel_data, pd.DataFrame([row_data])], ignore_index=True
                    )

                    # Row index is the last row (0-based)
                    row_idx = len(self.excel_data) - 1
                else:
                    # If DataFrame doesn't exist yet, reload from Excel
                    self.load_excel_data(file_path, sheet_name)
                    # Get the new row index (Excel row minus header and 1-based index)
                    row_idx = new_row - 2
                    # Get row data
                    if row_idx < len(self.excel_data):
                        row_data = self.excel_data.iloc[row_idx].to_dict()
                    else:
                        # Manual construction if row index is out of bounds
                        row_data = {col: val for col, val in zip(columns, values)}

                # Remove backup after successful write
                if path.exists(backup_file):
                    remove(backup_file)
                    print("[DEBUG] Removed backup file after successful write")

                print(f"[DEBUG] Successfully added new row at index {row_idx}")
                return row_data, row_idx

            finally:
                if "wb" in locals():
                    wb.close()

        except Exception as e:
            print(f"[DEBUG] Error adding new row: {str(e)}")
            print(f"[DEBUG] Error details: {traceback.format_exc()}")

            # Try to restore from backup
            if "backup_file" in locals() and path.exists(backup_file):
                try:
                    copy2(backup_file, file_path)
                    print("[DEBUG] Restored from backup after error")
                except Exception as backup_e:
                    print(f"[DEBUG] Failed to restore from backup: {str(backup_e)}")

            raise
