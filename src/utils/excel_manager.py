from __future__ import annotations
from typing import Dict, Optional, Tuple, List, Any, Callable
import os
import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.hyperlink import Hyperlink
from PyQt6.QtCore import QObject, QReadWriteLock
from shutil import copy2
from os import path, remove
import traceback
from .path_utils import normalize_path, make_relative_path, split_drive_or_unc


class ExcelManager(QObject):
    """Manages Excel file operations and data caching."""

    def __init__(self) -> None:
        super().__init__()
        self.excel_data: Optional[pd.DataFrame] = None
        # Cache format: {(row_idx: int, col_idx: int): hyperlink_target: Optional[str]}
        self._hyperlink_cache: Dict[Tuple[int, int], Optional[str]] = {}
        self._cache_lock = QReadWriteLock()
        self._last_file: Optional[str] = None
        self._last_sheet: Optional[str] = None
        self._sheet_cache: Dict[str, list] = {}  # Cache for sheet names
        self._column_cache: Dict[str, list] = {}  # Cache for column names
        self._header_cache: Dict[str, Dict[str, int]] = {} # Cache for header {sheet_key: {col_name: col_idx}}

    def clear_caches(self) -> None:
        """Clear all cached data."""
        self._cache_lock.lockForWrite()
        try:
            self._hyperlink_cache.clear()
            self._last_file = None
            self._last_sheet = None
            self._sheet_cache.clear()
            self._column_cache.clear()
            self._header_cache.clear()
            self.excel_data = None
            print("[DEBUG] All caches cleared")
        finally:
            self._cache_lock.unlock()

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

            # Clear hyperlink cache (acquire lock)
            self._cache_lock.lockForWrite()
            try:
                self._hyperlink_cache.clear()
                print("[DEBUG] Hyperlink cache cleared during data load")
            finally:
                self._cache_lock.unlock()

            # Clear header cache for this sheet
            sheet_key = f"{file_path}:{sheet_name}"
            if sheet_key in self._header_cache:
                del self._header_cache[sheet_key]

            return True

        except Exception as e:
            print(f"[DEBUG] Error loading Excel data: {str(e)}")
            self.excel_data = None
            self._last_file = None
            self._last_sheet = None
            self._cache_lock.lockForWrite()
            try:
                self._hyperlink_cache.clear()
            finally:
                self._cache_lock.unlock()
            raise

    def preload_hyperlinks_async(
        self,
        file_path: str,
        sheet_name: str,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Preload all hyperlinks from the sheet into the cache asynchronously."""
        print(f"[DEBUG] Starting hyperlink preloading for {file_path} - {sheet_name}")
        self._cache_lock.lockForWrite()
        try:
            self._hyperlink_cache.clear()

            # Try to normalize path for network paths
            normalized_path = file_path
            if file_path.startswith("//") or file_path.startswith("\\\\"):
                try:
                    parts = file_path.replace("/", "\\").strip("\\").split("\\")
                    if len(parts) >= 2:
                        normalized_path = f"\\\\{parts[0]}\\{parts[1]}"
                        if len(parts) > 2:
                            normalized_path += "\\" + "\\".join(parts[2:])
                    print(f"[DEBUG] Normalized network path for preloading: {normalized_path}")
                except Exception as path_err:
                    print(f"[DEBUG] Path normalization error during preloading: {str(path_err)}")

            try:
                # Load workbook WITHOUT read_only=True to access hyperlinks
                wb = load_workbook(normalized_path, data_only=True)
            except Exception:
                print(f"[DEBUG] Failed preload with normalized path, trying original: {file_path}")
                try:
                    # Load workbook WITHOUT read_only=True to access hyperlinks
                    wb = load_workbook(file_path, data_only=True)
                except Exception as wb_err:
                    print(f"[DEBUG] Could not load workbook for preloading: {str(wb_err)}")
                    return # Exit if workbook can't be loaded

            try:
                ws = wb[sheet_name]
            except KeyError:
                print(f"[DEBUG] Sheet '{sheet_name}' not found during preloading.")
                wb.close()
                return
            except Exception as sheet_err:
                print(f"[DEBUG] Error accessing sheet during preloading: {str(sheet_err)}")
                wb.close()
                return

            total_rows = ws.max_row
            processed_rows = 0

            # Iterate through all cells to find hyperlinks
            for row_idx, row in enumerate(ws.iter_rows()): # 0-based index from iter_rows
                for col_idx, cell in enumerate(row): # 0-based index from row iteration
                    if cell.hyperlink:
                        try:
                            target = cell.hyperlink.target
                            # Store with 0-based indices
                            cache_key = (row_idx, col_idx)
                            self._hyperlink_cache[cache_key] = target
                            # --- Add Debug Print ---
                            print(f"[DEBUG PRELOAD] Added to cache: key={cache_key}, target='{target}'")
                            # --- End Debug Print ---
                        except Exception as link_err:
                            print(f"[DEBUG] Error reading hyperlink at ({row_idx}, {col_idx}): {str(link_err)}")
                            self._hyperlink_cache[(row_idx, col_idx)] = None # Mark as checked but failed

                processed_rows += 1
                if progress_callback and total_rows > 0 and processed_rows % 100 == 0: # Report every 100 rows
                    progress = int((processed_rows / total_rows) * 100)
                    progress_callback(progress)

            wb.close()
            print(f"[DEBUG] Finished hyperlink preloading. Cached {len(self._hyperlink_cache)} links.")
            if progress_callback:
                progress_callback(100) # Signal completion

        except Exception as e:
            print(f"[DEBUG] Error during hyperlink preloading: {str(e)}")
            # Keep potentially partially filled cache? Or clear? Clearing seems safer.
            self._hyperlink_cache.clear()
        finally:
            self._cache_lock.unlock()

    def refresh_hyperlink_cache(
        self,
        file_path: str,
        sheet_name: str,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Force a refresh of the hyperlink cache."""
        print("[DEBUG] Refreshing hyperlink cache...")
        # This can be called directly, potentially in a separate thread if needed
        self.preload_hyperlinks_async(file_path, sheet_name, progress_callback)

    def get_hyperlink(self, row_idx: int, col_idx: int) -> Optional[str]:
        """Get hyperlink target from cache using 0-based indices.

        Args:
            row_idx: 0-based row index.
            col_idx: 0-based column index.

        Returns:
            Optional[str]: Hyperlink target or None if not found/cached.
        """
        self._cache_lock.lockForRead()
        try:
            link = self._hyperlink_cache.get((row_idx, col_idx))
            # print(f"[DEBUG] Cache lookup for ({row_idx}, {col_idx}): {'Found' if link else 'Not Found'}")
            return link
        finally:
            self._cache_lock.unlock()

    def _get_column_index(self, file_path: str, sheet_name: str, column_name: str) -> Optional[int]:
        """Get the 0-based index for a column name, using cache."""
        sheet_key = f"{file_path}:{sheet_name}"
        if sheet_key not in self._header_cache:
            try:
                wb = load_workbook(file_path, read_only=True)
                ws = wb[sheet_name]
                header = {cell.value: idx for idx, cell in enumerate(ws[1])} # 0-based index
                self._header_cache[sheet_key] = header
                wb.close()
            except Exception as e:
                print(f"[DEBUG] Error caching header for {sheet_key}: {str(e)}")
                return None

        return self._header_cache[sheet_key].get(column_name)

    def update_pdf_link(
        self,
        file_path: str,
        sheet_name: str,
        row_idx: int, # 0-based row index
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

            # Normalize paths using path_utils
            normalized_excel_path = normalize_path(file_path)
            normalized_pdf_path = normalize_path(pdf_path)

            print(f"[DEBUG] Linking to PDF: {normalized_pdf_path}")

            # Load workbook
            wb = load_workbook(file_path)
            ws = wb[sheet_name]

            # Find the column index (0-based) using helper
            col_idx_0_based = self._get_column_index(file_path, sheet_name, column_name)
            if col_idx_0_based is None:
                raise ValueError(f"Column '{column_name}' not found")
            col_idx_1_based = col_idx_0_based + 1 # openpyxl uses 1-based index

            # Get the cell
            excel_row_1_based = row_idx + 2  # +1 for header, +1 for 1-based index
            cell = ws.cell(row=excel_row_1_based, column=col_idx_1_based)

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

            # Use path_utils to determine if paths are on same drive/mount
            excel_drive, _ = split_drive_or_unc(normalized_excel_path)
            pdf_drive, _ = split_drive_or_unc(normalized_pdf_path)

            print(f"[DEBUG] Excel mount: {excel_drive}, PDF mount: {pdf_drive}")

            # Calculate target path using path_utils make_relative_path
            target_path = make_relative_path(normalized_excel_path, normalized_pdf_path)
            print(f"[DEBUG] Target path for hyperlink: {target_path}")

            # Update hyperlink using Excel formula and styling
            hyperlink = Hyperlink(ref=cell.coordinate, target=target_path)
            hyperlink.target_mode = "file"
            cell.hyperlink = hyperlink
            cell.style = "Hyperlink"

            # Save workbook
            wb.save(file_path)
            print(f"[DEBUG] Set HYPERLINK formula: {cell.value}")
            print(f"[DEBUG] Updated Excel hyperlink, original: {original_link}")
            print("[DEBUG] Excel file saved successfully")

            # Update cache (acquire lock)
            self._cache_lock.lockForWrite()
            try:
                # Use 0-based indices for cache key
                self._hyperlink_cache[(row_idx, col_idx_0_based)] = target_path
                print(f"[DEBUG] Updated cache for ({row_idx}, {col_idx_0_based})")
            finally:
                self._cache_lock.unlock()

            return original_link

        except Exception as e:
            print(f"[DEBUG] Error updating PDF link: {str(e)}")
            return None

    def revert_pdf_link(
        self,
        excel_file: str,
        sheet_name: str,
        row_idx: int, # 0-based row index
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

            # Find the column index (0-based) using helper
            col_idx_0_based = self._get_column_index(excel_file, sheet_name, filter2_col)
            if col_idx_0_based is None:
                raise ValueError(f"Column '{filter2_col}' not found")
            col_idx_1_based = col_idx_0_based + 1 # openpyxl uses 1-based index

            # Get the cell
            excel_row_1_based = row_idx + 2 # +1 header, +1 for 1-based index
            cell = ws.cell(row=excel_row_1_based, column=col_idx_1_based)
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

            # Update cache (acquire lock)
            self._cache_lock.lockForWrite()
            try:
                # Use 0-based indices for cache key
                cache_key = (row_idx, col_idx_0_based)
                if original_hyperlink:
                    self._hyperlink_cache[cache_key] = original_hyperlink
                    print(f"[DEBUG] Updated cache for {cache_key} with original link")
                elif cache_key in self._hyperlink_cache:
                    del self._hyperlink_cache[cache_key]
                    print(f"[DEBUG] Removed cache entry for {cache_key}")
            finally:
                self._cache_lock.unlock()

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
