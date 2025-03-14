from __future__ import annotations
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import time
import pandas as pd
import os

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSplitter,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from ..utils import ConfigManager, ExcelManager, PDFManager, PDFTask
from .fuzzy_search import FuzzySearchFrame
from .queue_display import QueueDisplay
from .pdf_viewer import PDFViewer
from .error_dialog import ErrorDialog

class ProcessingThread(QThread):
    """Background thread for processing PDFs."""
    
    task_completed = pyqtSignal(str, str)  # task_id, status
    task_failed = pyqtSignal(str, str)     # task_id, error_message
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.tasks: Dict[str, PDFTask] = {}
        self.running = True
        # Cache for Excel data to avoid reloading for every task
        self._excel_data_cache = {
            'file': None,
            'sheet': None,
            'data': None,
            'columns': None
        }
    
    def run(self) -> None:
        """Process tasks in the queue."""
        while self.running:
            # Find next pending task
            task_to_process = None
            task_id = None
            
            for id, task in self.tasks.items():
                if task.status == "pending":
                    task_to_process = task
                    task_id = id
                    task.status = "processing"
                    break
            
            if not task_to_process:
                time.sleep(0.1)
                continue
            
            try:
                print(f"[DEBUG] Processing task {task_id}: {task_to_process.pdf_path}")
                
                # Access the config manager and other required components
                parent = self.parent()
                if not parent or not hasattr(parent, 'config_manager'):
                    raise Exception("Could not access configuration")
                    
                config = parent.config_manager.get_config()
                excel_manager = parent.excel_manager
                pdf_manager = parent.pdf_manager
                
                # Verify required configuration
                required_configs = ["processed_folder", "output_template", "excel_file", "excel_sheet"]
                missing_configs = [cfg for cfg in required_configs if not config.get(cfg)]
                if missing_configs:
                    raise Exception(f"Missing required configuration: {', '.join(missing_configs)}")
                
                # Load Excel data with caching for efficiency
                self._ensure_excel_data_loaded(excel_manager, config)
                df = self._excel_data_cache['data']
                
                # Get filter columns based on number of filter values
                filter_columns = self._get_filter_columns(config, task_to_process.filter_values)
                
                # Make a copy of filter values to avoid modifying the original
                filter_values = task_to_process.filter_values.copy()
                
                # Find row index efficiently
                try:
                    row_idx = self._find_matching_row(df, filter_columns, filter_values, task_to_process)
                except Exception as e:
                    print(f"[DEBUG] Error finding matching row: {str(e)}")
                    raise Exception(f"Could not find matching Excel row: {str(e)}")
                
                # Update task with the row index
                task_to_process.row_idx = row_idx
                
                # Extract and validate row data
                if row_idx >= len(df):
                    print(f"[DEBUG] Row index {row_idx} is out of bounds (df length: {len(df)}). Reloading Excel data.")
                    # Reload Excel data to ensure we have the latest
                    excel_manager.load_excel_data(config["excel_file"], config["excel_sheet"])
                    df = excel_manager.excel_data
                    # Update cache
                    self._excel_data_cache['data'] = df
                    
                    # Check again after reload
                    if row_idx >= len(df):
                        raise Exception(f"Row index {row_idx} is still out of bounds after reloading Excel data (df length: {len(df)})")
                
                row_data = df.iloc[row_idx]
                try:
                    self._validate_row_data(row_data, filter_columns, filter_values)
                except Exception as e:
                    print(f"[DEBUG] Row data validation error: {str(e)}")
                    raise Exception(f"Row data validation failed: {str(e)}")
                
                # Create template data from row data efficiently
                template_data = self._create_template_data(row_data, filter_columns, filter_values, row_idx)
                
                # Add processed_folder to template data
                template_data["processed_folder"] = config["processed_folder"]
                
                # Process steps with individual try-except blocks to allow partial success
                
                # Step 1: Generate output path
                processed_path = None
                try:
                    processed_path = pdf_manager.generate_output_path(
                        config["output_template"], 
                        template_data
                    )
                    print(f"[DEBUG] Step 1 - Generated output path: {processed_path}")
                except Exception as e:
                    print(f"[DEBUG] Error generating output path: {str(e)}")
                    raise Exception(f"Failed to generate output path: {str(e)}")
                
                # Step 2: Update Excel hyperlink
                try:
                    original_link = self._update_excel_hyperlink(
                        excel_manager, 
                        config, 
                        row_idx, 
                        processed_path,
                        filter_columns[1] if len(filter_columns) > 1 else None,
                        task_to_process
                    )
                    print(f"[DEBUG] Step 2 - Updated Excel hyperlink, original: {original_link}")
                except Exception as e:
                    print(f"[DEBUG] Warning - Excel hyperlink update failed: {str(e)}")
                    # Continue even if hyperlink update fails
                
                # Step 3: Process the PDF
                try:
                    pdf_manager.process_pdf(
                        task=task_to_process,
                        template_data=template_data,
                        processed_folder=config["processed_folder"],
                        output_template=config["output_template"]
                    )
                    print(f"[DEBUG] Step 3 - PDF processed successfully")
                    
                    # Set completed status before emitting signal
                    task_to_process.status = "completed"
                    task_to_process.end_time = datetime.now()
                    
                    # Task completed successfully
                    self.task_completed.emit(task_id, "completed")
                    print(f"[DEBUG] Task {task_id} completed successfully")
                    
                except Exception as e:
                    print(f"[DEBUG] Error processing PDF: {str(e)}")
                    raise Exception(f"PDF processing failed: {str(e)}")
                
            except Exception as e:
                error_msg = str(e)
                print(f"[DEBUG] Task processing error: {error_msg}")
                
                # Update task status before emitting signal
                if task_id in self.tasks:
                    self.tasks[task_id].status = "failed"
                    self.tasks[task_id].error_msg = error_msg
                    self.tasks[task_id].end_time = datetime.now()
                
                # Emit failure signal with the actual error message
                self.task_failed.emit(task_id, error_msg)
                print(f"[DEBUG] Task {task_id} failed: {error_msg}")
                
            finally:
                # Small delay to prevent CPU overuse
                time.sleep(0.05)  # Reduced from 0.1 for better throughput
    
    def _ensure_excel_data_loaded(self, excel_manager, config):
        """Ensure Excel data is loaded, using cache if possible."""
        excel_file = config["excel_file"]
        excel_sheet = config["excel_sheet"]
        
        # Check if we need to reload the data
        if (self._excel_data_cache['file'] != excel_file or 
            self._excel_data_cache['sheet'] != excel_sheet or
            self._excel_data_cache['data'] is None):
            
            # Load new data
            excel_manager.load_excel_data(excel_file, excel_sheet)
            
            # Update cache
            self._excel_data_cache['file'] = excel_file
            self._excel_data_cache['sheet'] = excel_sheet
            self._excel_data_cache['data'] = excel_manager.excel_data
            # Pre-convert all string columns to strings to avoid repeated conversions
            for col in self._excel_data_cache['data'].select_dtypes(exclude=['datetime64']):
                self._excel_data_cache['data'][col] = self._excel_data_cache['data'][col].astype(str)
    
    def _get_filter_columns(self, config, filter_values):
        """Get filter columns based on filter values."""
        filter_columns = []
        for i in range(1, len(filter_values) + 1):
            column_key = f"filter{i}_column"
            if column_key not in config:
                raise Exception(f"Missing filter column configuration for filter {i}")
            filter_columns.append(config[column_key])
        return filter_columns
    
    def _find_matching_row(self, df, filter_columns, filter_values, task=None):
        """Find the matching row in Excel data based on filter values."""
        if len(filter_values) < 2 or len(filter_columns) < 2:
            raise Exception("At least two filter values are required")
        
        # Check if the task already has a valid row_idx set
        if task and task.row_idx >= 0 and task.row_idx < len(df):
            # Verify that the row contains the expected filter2 value
            filter2_column = filter_columns[1]
            filter2_value = filter_values[1]
            actual_value = str(df.iloc[task.row_idx][filter2_column])
            
            if actual_value == filter2_value:
                print(f"[DEBUG] Using pre-set task row_idx {task.row_idx} (Excel row {task.row_idx + 2})")
                return task.row_idx
            else:
                print(f"[DEBUG] Pre-set row_idx {task.row_idx} does not match filter2 value. Expected: {filter2_value}, Got: {actual_value}")
                # Continue with normal processing since the row doesn't match
        
        # Get filter2 value - if it has Excel row info, extract it
        filter2_value = filter_values[1]
        parent = self.parent()
        row_idx = -1
        
        # If filter2 value contains the Excel row marker, parse it
        if isinstance(filter2_value, str) and "⟨Excel Row:" in filter2_value:
            print(f"[DEBUG] Parsing filter2 value with row info: {filter2_value}")
            
            # If parent exists and has the parse method, use it to extract row info
            if parent and hasattr(parent, '_parse_filter2_value'):
                # Parse filter2 value to extract clean value and row index
                clean_value, extracted_row_idx = parent._parse_filter2_value(filter2_value)
                if extracted_row_idx >= 0:
                    # Use the row index from the formatted value
                    print(f"[DEBUG] Using extracted row index: {extracted_row_idx}")
                    row_idx = extracted_row_idx
                    filter2_value = clean_value
                    filter_values[1] = clean_value  # Replace with clean value for further processing
                    
            # If we have a valid row index from the formatted value, verify it
            if row_idx >= 0:
                # Verify that the row contains the expected filter2 value
                if row_idx < len(df):
                    filter2_column = filter_columns[1]
                    actual_value = str(df.iloc[row_idx][filter2_column])
                    if actual_value == filter2_value:
                        print(f"[DEBUG] Found matching row at index {row_idx}")
                        return row_idx
                    else:
                        print(f"[DEBUG] Row index {row_idx} does not match filter2 value. Expected: {filter2_value}, Got: {actual_value}")
                else:
                    print(f"[DEBUG] Row index {row_idx} is out of bounds (df length: {len(df)})")
                    
            # If row index from formatted value doesn't work, fall back to search
            filter2_column = filter_columns[1]
            print(f"[DEBUG] Searching for rows with filter2 value: '{filter2_value}' in column '{filter2_column}'")
            
            # Use vectorized operations for better performance
            matching_mask = df[filter2_column].astype(str) == filter2_value
            matching_rows = df[matching_mask]
            
            matching_count = len(matching_rows)
            print(f"[DEBUG] Found {matching_count} matching rows for filter2 value")
            
            if matching_count == 0:
                raise Exception(f"Could not find Excel row matching filter value: {filter2_value}")
                
            if matching_count == 1:
                # Found exactly one match
                row_idx = matching_rows.index[0]
                print(f"[DEBUG] Found unique matching row at index {row_idx}")
                return row_idx
                
            # Multiple matches - try to narrow down using other filters
            print(f"[DEBUG] Found multiple matches, narrowing down with other filters")
            # Start with all matching rows from filter2
            multi_filter_mask = matching_mask.copy()
            
            # Apply additional filters
            for i, (col, val) in enumerate(zip(filter_columns, filter_values)):
                if i != 1:  # Skip filter2 which we already used
                    print(f"[DEBUG] Applying additional filter: {col}={val}")
                    multi_filter_mask &= (df[col].astype(str) == str(val))
                    narrowed_count = multi_filter_mask.sum()
                    print(f"[DEBUG] After filter {i+1}, {narrowed_count} matches remain")
                    # Check if we have a unique match after adding this filter
                    if narrowed_count == 1:
                        row_idx = df[multi_filter_mask].index[0]
                        print(f"[DEBUG] Found unique matching row at index {row_idx} after applying all filters")
                        return row_idx
            
            # If we still have multiple matches, use the first one
            if multi_filter_mask.sum() > 0:
                row_idx = df[multi_filter_mask].index[0]
                print(f"[DEBUG] Using first of multiple matches at index {row_idx}")
                return row_idx
                
            # Fall back to the first match from filter2 if the combined filters yielded no results
            row_idx = matching_rows.index[0]
            print(f"[DEBUG] Falling back to first filter2 match at index {row_idx}")
            return row_idx
        else:
            # No Excel row specified in the filter2 value, automatically add a new row
            print(f"[DEBUG] Using direct filter2 value (no row info): {filter2_value}")
            print(f"[DEBUG] No Excel row specified - automatically adding new row")
            try:
                # Get configuration
                config = {}
                if parent and hasattr(parent, 'config_manager'):
                    config = parent.config_manager.get_config()
                
                # Create a new row with the filter values
                filter_values_copy = filter_values.copy()
                filter_values_copy[1] = filter2_value  # Use the raw value without formatting
                
                # Use the excel manager to add the new row
                excel_manager = None
                if parent and hasattr(parent, 'excel_manager'):
                    excel_manager = parent.excel_manager
                elif hasattr(self, 'excel_manager'):
                    excel_manager = self.excel_manager
                
                if not excel_manager:
                    raise Exception("Excel manager not available")
                
                new_row_data, new_row_idx = excel_manager.add_new_row(
                    config["excel_file"],
                    config["excel_sheet"],
                    filter_columns,
                    filter_values_copy
                )
                
                # Update row_idx with the new row information
                row_idx = new_row_idx
                
                # Update the cached DataFrame to include the new row
                # This ensures df.iloc[row_idx] will work after adding a new row
                self._excel_data_cache['data'] = excel_manager.excel_data
                
                # Update filter2 value with formatted value including row info
                if parent and hasattr(parent, '_format_filter2_value'):
                    filter_values[1] = parent._format_filter2_value(filter2_value, row_idx, False)
                
                print(f"[DEBUG] Added new row {row_idx} for filter2 value '{filter2_value}'")
                return row_idx
            except Exception as e:
                print(f"[DEBUG] Failed to automatically add new row: {str(e)}")
                raise Exception(f"Failed to automatically add new row for filter value: {filter2_value}. Error: {str(e)}")
    
    def _validate_row_data(self, row_data, filter_columns, filter_values):
        """Validate that row data matches filter values."""
        # Skip validation if task's row_idx was directly obtained from filter2 row info
        parent = self.parent()
        if parent and hasattr(parent, "_parse_filter2_value") and len(filter_values) > 1:
            # Check if we originally had a row number in filter2
            formatted_filter2 = self.parent().filter_frames[1]["fuzzy"].get() if hasattr(self.parent(), "filter_frames") else None
            if formatted_filter2 and "⟨Excel Row:" in formatted_filter2:
                # We have a direct row reference, skip strict validation
                print(f"[DEBUG] Using row directly from filter2 row info, skipping strict validation")
                return True
        
        if len(filter_columns) < 2:
            return  # Not enough filters to validate
            
        mismatched_filters = []
        date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]
        
        print(f"[DEBUG] Validating row data against filter values")
        for i, (col, val) in enumerate(zip(filter_columns, filter_values)):
            if i != 1:  # Skip filter2 which we already used for finding the row
                row_value = row_data[col]
                
                # Handle date values more intelligently
                if "DATE" in col.upper() and pd.notna(row_value):
                    # Try to normalize both values to a common date format for comparison
                    row_date = self._normalize_date(row_value, date_formats)
                    filter_date = self._normalize_date(val, date_formats)
                    
                    if row_date and filter_date and row_date == filter_date:
                        # Dates match when normalized
                        print(f"[DEBUG] Date match in column {col} after normalization: '{val}' ≈ '{row_value}'")
                    elif filter_date is None:
                        # Couldn't parse filter value as date, fall back to string comparison
                        formatted_value = self._format_date_value(row_value, date_formats)
                        if formatted_value != str(val).strip():
                            print(f"[DEBUG] Date mismatch in column {col}: expected '{val}', got '{formatted_value}'")
                            mismatched_filters.append(f"{col}: expected '{val}', got '{formatted_value}'")
                        else:
                            print(f"[DEBUG] Value match in column {col}: '{val}'")
                    else:
                        # Dates don't match even after normalization
                        print(f"[DEBUG] Date mismatch in column {col}: expected '{val}' ({filter_date}), got '{row_value}' ({row_date})")
                        mismatched_filters.append(f"{col}: expected '{val}' ({filter_date}), got '{row_value}' ({row_date})")
                elif str(row_value).strip() != str(val).strip():
                    print(f"[DEBUG] Value mismatch in column {col}: expected '{val}', got '{row_value}'")
                    mismatched_filters.append(f"{col}: expected '{val}', got '{row_value}'")
                else:
                    print(f"[DEBUG] Value match in column {col}: '{val}'")
        
        if mismatched_filters:
            print(f"[DEBUG] Validation failed with mismatches: {mismatched_filters}")
            
            # If date format issues are the only problems, warn but don't fail
            only_date_issues = all("DATE" in mismatch.split(':')[0] for mismatch in mismatched_filters)
            if only_date_issues:
                print(f"[DEBUG] Only date format mismatches found, continuing with processing")
                return True
                
            raise Exception(f"Selected row data doesn't match filter values: {', '.join(mismatched_filters)}")
        
        print(f"[DEBUG] Row data validation successful")
        return True
    
    def _normalize_date(self, value, date_formats):
        """Normalize a date value to ISO format (YYYY-MM-DD) for consistent comparison.
        
        Returns:
            The normalized date string, or None if parsing fails
        """
        # Already a datetime object
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        
        # Try parsing as date string
        value_str = str(value).strip()
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(value_str, date_format)
                return parsed_date.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                continue
        
        return None
    
    def _format_date_value(self, value, date_formats):
        """Format a date value for consistent comparison."""
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        
        # Try parsing as date
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(str(value).strip(), date_format)
                return parsed_date.strftime("%d/%m/%Y")
            except (ValueError, TypeError):
                continue
        
        # Fall back to string representation
        return str(value).strip()
    
    def _create_template_data(self, row_data, filter_columns, filter_values, row_idx=None):
        """Create template data dict from row data efficiently.
        
        Args:
            row_data: Excel row data
            filter_columns: List of column names for filters
            filter_values: List of filter values
            row_idx: Optional row index (0-based)
            
        Returns:
            Dict with template data
        """
        template_data = {}
        date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]
        
        # Add filter values to template data
        for i, (column, value) in enumerate(zip(filter_columns, filter_values), 1):
            # For filter2, include Excel row in the value
            if i == 2 and row_idx is not None:
                parent = self.parent()
                if parent and hasattr(parent, '_format_filter2_value'):
                    excel_row = row_idx + 2  # Convert to Excel row (1-based + header)
                    formatted_value = value + f" ⟨Excel Row: {excel_row}⟩"
                    template_data[f"filter{i}"] = formatted_value
                else:
                    template_data[f"filter{i}"] = value
            else:
                template_data[f"filter{i}"] = value
                
            template_data[column] = value
            
            # Try to convert date string values to datetime objects
            if isinstance(value, str):
                for fmt in date_formats:
                    try:
                        date_obj = datetime.strptime(value, fmt)
                        template_data[f"filter{i}_date"] = date_obj
                        print(f"[DEBUG] Converted filter{i} to datetime: {date_obj}")
                        break
                    except ValueError:
                        continue
        
        # Get rest of the data from the row
        for column in row_data.index:
            if column not in template_data:
                value = row_data[column]
                template_data[column] = value
                
                # Try to convert date values to datetime objects
                if isinstance(value, str):
                    for fmt in date_formats:
                        try:
                            date_obj = datetime.strptime(value, fmt)
                            template_data[f"{column}_date"] = date_obj
                            print(f"[DEBUG] Converted {column} to datetime: {date_obj}")
                            break
                        except ValueError:
                            continue
                elif isinstance(value, pd.Timestamp):
                    # Convert pandas Timestamp to Python datetime
                    template_data[f"{column}_date"] = value.to_pydatetime()
                    print(f"[DEBUG] Converted pandas Timestamp {column} to datetime")
        
        # Add the current date and time
        template_data["current_date"] = datetime.now()
        
        print(f"[DEBUG] Created template data with {len(template_data)} keys")
        return template_data
    
    def _update_excel_hyperlink(self, excel_manager, config, row_idx, processed_path, filter_column, task):
        """Update Excel hyperlink with error handling."""
        try:
            # Store original Excel row index in task
            task.row_idx = row_idx
            
            original_hyperlink = excel_manager.update_pdf_link(
                config["excel_file"],
                config["excel_sheet"],
                row_idx,
                processed_path,
                filter_column
            )
            
            # Store original hyperlink for potential revert operation
            task.original_excel_hyperlink = original_hyperlink
            task.original_pdf_location = task.pdf_path
            
            # Also store the processed file location
            task.processed_pdf_location = processed_path
            
            print(f"[DEBUG] Updated Excel hyperlink for row {row_idx}, original: {original_hyperlink}")
            
            return original_hyperlink
            
        except Exception as e:
            print(f"Warning: Could not update Excel hyperlink: {str(e)}")
            # Continue processing even if hyperlink update fails
    
    def stop(self) -> None:
        """Stop the processing thread."""
        self.running = False
        self.wait()

class ProcessingTab(QWidget):
    """Tab for processing PDF files."""
    
    _instance = None  # Class-level instance tracking
    
    @classmethod
    def get_instance(cls) -> Optional[ProcessingTab]:
        """Get the current ProcessingTab instance."""
        return cls._instance
    
    def __init__(
        self,
        config_manager: ConfigManager,
        excel_manager: ExcelManager,
        pdf_manager: PDFManager,
        error_handler: Callable[[Exception, str], None],
        status_handler: Callable[[str], None],
    ) -> None:
        super().__init__()
        ProcessingTab._instance = self
        
        # Store managers and handlers
        self.config_manager = config_manager
        self.excel_manager = excel_manager
        self.pdf_manager = pdf_manager
        self._handle_error = error_handler
        self._update_status = status_handler
        
        # Initialize state
        self._pending_config_change_id = None
        self._is_reloading = False
        self.current_pdf: Optional[str] = None
        self.current_pdf_start_time: Optional[datetime] = None
        self.filter_frames = []
        
        # Initialize processing thread before UI setup
        self.processing_thread = ProcessingThread(self)
        self.processing_thread.task_completed.connect(self._on_task_completed)
        self.processing_thread.task_failed.connect(self._on_task_failed)
        self.processing_thread.start()
        
        # Clean up any processed files from previous runs
        self._cleanup_processed_files()
        
        # Create UI
        self._setup_ui()
        
        # Register for config changes
        self.config_manager.config_changed.connect(self._on_config_change)
    
    def _cleanup_processed_files(self) -> None:
        """Clean up any processed files from previous runs."""
        config = self.config_manager.get_config()
        source_folder = config.get("source_folder")
        if source_folder:
            try:
                self.pdf_manager.cleanup_processed_files(source_folder)
            except Exception as e:
                print(f"[DEBUG] Error during cleanup of processed files: {str(e)}")
                # Continue even if cleanup fails
    
    def _create_section_frame(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled frame for a section."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        
        if title:
            label = QLabel(title)
            label.setStyleSheet("font-weight: bold; font-size: 12pt;")
            layout.addWidget(label)
        
        return frame, layout
    
    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Create splitter for main panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel (Filters and Actions)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Filters section
        filters_frame, filters_layout = self._create_section_frame("Filters")
        
        self.filters_container = QWidget()
        self.filters_layout = QVBoxLayout(self.filters_container)
        filters_layout.addWidget(self.filters_container)
        
        left_layout.addWidget(filters_frame)
        
        # Actions section
        actions_frame, actions_layout = self._create_section_frame("Actions")
        
        # Process button
        self.process_button = QPushButton("Process File")
        self.process_button.clicked.connect(self._process_current_file)
        self.process_button.setEnabled(False)
        # Make the process button the default button so it responds to Enter key press
        self.process_button.setDefault(True)
        self.process_button.setAutoDefault(True)
        # Add focus style
        self.process_button.setStyleSheet("""
            QPushButton:focus {
                background-color: #cce4ff;
                border: 2px solid #007bff;
            }
        """)
        actions_layout.addWidget(self.process_button)
        
        # Skip button
        self.skip_button = QPushButton("Skip File")
        self.skip_button.clicked.connect(lambda: self._load_next_pdf(skip=True))
        actions_layout.addWidget(self.skip_button)
        
        left_layout.addWidget(actions_frame)
        left_layout.addStretch()
        
        # Center panel (PDF Viewer)
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        # PDF viewer section
        viewer_frame, viewer_layout = self._create_section_frame("PDF Viewer")
        
        # PDF viewer
        self.pdf_viewer = PDFViewer(self.pdf_manager)
        viewer_layout.addWidget(self.pdf_viewer)
        
        center_layout.addWidget(viewer_frame)
        
        # Right panel (Queue)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Queue section
        queue_frame, queue_layout = self._create_section_frame("Processing Queue")
        
        # Queue display
        self.queue_display = QueueDisplay()
        self.queue_display.clear_button.clicked.connect(self._clear_completed)
        self.queue_display.retry_button.clicked.connect(self._retry_failed)
        queue_layout.addWidget(self.queue_display)
        
        right_layout.addWidget(queue_frame)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        
        # Set initial sizes (proportional)
        splitter.setSizes([200, 600, 200])
        
        # Load initial data
        self._setup_filters()
        self._load_next_pdf()
        
        # Start periodic updates
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_display)
        self._update_timer.start(500)  # Update every 500ms
    
    def _setup_filters(self) -> None:
        """Setup filter controls based on configuration."""
        config = self.config_manager.get_config()
        
        # Clear existing filters
        for frame in self.filter_frames:
            frame["frame"].deleteLater()
        self.filter_frames.clear()
        
        # Create new filters
        i = 1
        while True:
            filter_key = f"filter{i}_column"
            if filter_key not in config:
                break
                
            column = config[filter_key]
            
            # Create frame and layout
            frame, layout = self._create_section_frame("")
            
            # Add label
            label = QLabel(column)
            label.setStyleSheet("font-weight: bold;")
            layout.addWidget(label)
            
            # Create fuzzy search
            fuzzy = FuzzySearchFrame(
                identifier=f"processing_filter{i}",
                on_tab=lambda e, idx=i-1: self._handle_filter_tab(e, idx)
            )
            # Connect value_selected signal to update dependent filters
            fuzzy.value_selected.connect(lambda idx=i-1: self._on_filter_selected(idx))
            layout.addWidget(fuzzy)
            
            # Add to main layout
            self.filters_layout.addWidget(frame)
            
            # Store filter info
            self.filter_frames.append({
                "frame": frame,
                "label": label,
                "fuzzy": fuzzy,
                "column": column
            })
            
            i += 1
        
        # Add stretch at the end
        self.filters_layout.addStretch()
        
        # Load initial values for first filter
        if self.filter_frames:
            self._load_filter_values(0)
    
    def _format_filter2_value(self, value: str, row_idx: int, has_hyperlink: bool = False) -> str:
        """Format filter2 value with row number and checkmark if hyperlinked.
        
        Args:
            value: The original filter value
            row_idx: The 0-based row index in Excel
            has_hyperlink: Whether the corresponding Excel cell has a hyperlink
            
        Returns:
            Formatted string with checkmark (if applicable) and row information
        """
        prefix = "✓ " if has_hyperlink else ""
        # +2 because Excel is 1-based and has header
        return f"{prefix}{value} ⟨Excel Row: {row_idx + 2}⟩"
    
    def _parse_filter2_value(self, formatted_value: str) -> tuple[str, int]:
        """Parse filter2 value to get original value and row number.
        
        Args:
            formatted_value: String in format "✓ value ⟨Excel Row: N⟩"
            
        Returns:
            tuple[str, int]: (original value without formatting, 0-based row index)
        """
        import re
        if not formatted_value:
            print("[DEBUG] UI received empty filter2 value")
            return "", -1
            
        # Remove checkmark if present
        formatted_value = formatted_value.replace("✓ ", "", 1)
        match = re.match(r"(.*?)\s*⟨Excel Row:\s*(\d+)⟩", formatted_value)
        if match:
            value = match.group(1).strip()
            row_num = int(match.group(2))
            print(f"[DEBUG] UI parsed filter2 value: '{formatted_value}' -> value='{value}', row={row_num - 2}")
            return value, row_num - 2  # Convert back to 0-based index
            
        print(f"[DEBUG] UI failed to parse filter2 value: '{formatted_value}'")
        return formatted_value, -1
    
    def _load_filter_values(self, filter_index: int = 0) -> None:
        """Load values for a specific filter.
        
        Args:
            filter_index: Index of the filter to load values for (0-based)
        """
        try:
            config = self.config_manager.get_config()
            if not (config["excel_file"] and config["excel_sheet"]):
                return
                
            # Load Excel data if needed
            if self.excel_manager.excel_data is None:
                self.excel_manager.load_excel_data(
                    config["excel_file"],
                    config["excel_sheet"]
                )
            
            # If we have no filters, exit
            if not self.filter_frames or filter_index >= len(self.filter_frames):
                return
                
            # Get the dataframe
            df = self.excel_manager.excel_data
            
            # Apply filters for all previous filters
            filtered_df = df.copy()
            for i in range(filter_index):
                # Skip if we don't have a value for this filter
                selected_value = self.filter_frames[i]["fuzzy"].get()
                if not selected_value:
                    continue
                
                # If this is filter2, parse it to get the clean value
                if i == 1:
                    clean_value, _ = self._parse_filter2_value(selected_value)
                    selected_value = clean_value
                    
                # Apply filter
                column = self.filter_frames[i]["column"]
                filtered_df = filtered_df[filtered_df[column].astype(str) == selected_value]
            
            # Get values for the current filter
            column = self.filter_frames[filter_index]["column"]
            
            # Special handling for filter2 - show ALL rows, not just unique values
            if filter_index == 1:
                # Cache hyperlinks for the filter2 column
                self.excel_manager.cache_hyperlinks_for_column(
                    config["excel_file"],
                    config["excel_sheet"],
                    column
                )
                
                # Get all rows from filtered_df, not just unique values
                formatted_values = []
                
                # Process each row individually
                for idx, row in filtered_df.iterrows():
                    value = str(row[column]).strip()
                    has_hyperlink = self.excel_manager.has_hyperlink(idx)
                    formatted_value = self._format_filter2_value(value, idx, has_hyperlink)
                    formatted_values.append(formatted_value)
                
                # Sort the formatted values for better user experience
                formatted_values.sort()
                values = formatted_values
            else:
                # For other filters, keep using unique values
                values = sorted(filtered_df[column].astype(str).unique().tolist())
            
            # Update the fuzzy search values
            values = [str(x).strip() for x in values]
            self.filter_frames[filter_index]["fuzzy"].set_values(values)
                
        except Exception as e:
            self._handle_error(e, f"loading filter values for filter {filter_index+1}")
    
    def _on_filter_selected(self, filter_index: int) -> None:
        """Handle selection in a filter.
        
        Args:
            filter_index: Index of the filter where selection occurred (0-based)
        """
        # Update process button state
        self._update_process_button()
        
        # If this is the last filter, nothing to cascade
        if filter_index >= len(self.filter_frames) - 1:
            return
            
        # Clear all subsequent filters
        for i in range(filter_index + 1, len(self.filter_frames)):
            self.filter_frames[i]["fuzzy"].clear()
        
        # Update next filter's values
        self._load_filter_values(filter_index + 1)
    
    def _handle_filter_tab(self, event: Any, filter_index: int) -> str:
        """Handle tab key in filter."""
        if filter_index < len(self.filter_frames) - 1:
            # Move to next filter
            self.filter_frames[filter_index + 1]["fuzzy"].entry.setFocus()
        else:
            # Move to process button and visually highlight it
            self.process_button.setFocus()
            # The button will be highlighted by the focus style in Qt
        return "break"
    
    def _process_current_file(self) -> None:
        """Process the current file."""
        if not self.current_pdf:
            self._update_status("No file selected")
            return
            
        # Get filter values
        filter_values = []
        formatted_filter_values = []  # Store the original formatted values
        
        for i, frame in enumerate(self.filter_frames):
            value = frame["fuzzy"].get()
            if not value:
                self._update_status("All filters must be set")
                return
                
            # Store the original formatted value
            formatted_filter_values.append(value)
                
            # For filter2, extract the clean value without formatting
            if i == 1:
                clean_value, row_idx = self._parse_filter2_value(value)
                print(f"[DEBUG] Processing filter2 value: '{value}' -> clean='{clean_value}', row={row_idx}")
                value = clean_value
                
            filter_values.append(value)
        
        # Store the current PDF path before closing it
        current_pdf_path = self.current_pdf
        
        # Clear the PDF from the viewer to release file handles
        self.pdf_viewer.clear_pdf()
        
        # Create task
        task = PDFTask(
            pdf_path=current_pdf_path,
            filter_values=filter_values,
            start_time=datetime.now()
        )
        
        # Store the row index if we have it
        if len(formatted_filter_values) > 1:
            _, row_idx = self._parse_filter2_value(formatted_filter_values[1])
            if row_idx >= 0:
                task.row_idx = row_idx
                print(f"[DEBUG] Pre-setting task row_idx to {row_idx} from filter2 value")
        
        # Add to processing queue
        self.processing_thread.tasks[task.task_id] = task
        
        print(f"[DEBUG] Added task {task.task_id} to queue with filter values: {filter_values}")
        
        # Load next file
        self._load_next_pdf()
    
    def _load_next_pdf(self, skip: bool = False) -> None:
        """Load the next PDF file."""
        try:
            print(f"[DEBUG] _load_next_pdf called with skip={skip}, current_pdf={self.current_pdf}")
            
            if skip and self.current_pdf:
                # Create skipped task
                task = PDFTask(
                    pdf_path=self.current_pdf,
                    status="skipped",
                    start_time=self.current_pdf_start_time or datetime.now(),
                    end_time=datetime.now()
                )
                self.processing_thread.tasks[task.task_id] = task
                
                # Mark the file as processed in our tracking
                self.pdf_manager.mark_file_processed(self.current_pdf)
            
            # If we have a current PDF, make sure to release it completely
            current_pdf = None
            if self.current_pdf:
                current_pdf = self.current_pdf
                
                # Clear the PDF from the viewer
                self.pdf_viewer.clear_pdf()
                
                # Reset our state variables
                self.current_pdf = None
                self.current_pdf_start_time = None
                
                # Force garbage collection
                import gc
                gc.collect()
            
            # Get next file
            config = self.config_manager.get_config()
            if not config["source_folder"]:
                self._update_status("Source folder not configured")
                return
                
            active_tasks = {
                k: v for k, v in self.processing_thread.tasks.items()
                if v.status in ["pending", "processing"]
            }
            
            # Temporary yield to let other operations complete
            QApplication.processEvents()
            
            # Now get the next PDF
            next_pdf = self.pdf_manager.get_next_pdf(
                config["source_folder"],
                active_tasks
            )
            
            # We don't need to check if we're reloading the same file here anymore,
            # because the get_next_pdf method already checks against processed files.
            # The warning was occurring because we were comparing the newly selected file
            # with the current file that was preloaded in the UI, not the one that was
            # actually just processed.
            
            if next_pdf:
                print(f"[DEBUG] Loading next PDF: {next_pdf}")
                self.current_pdf = next_pdf
                self.current_pdf_start_time = datetime.now()
                self.pdf_viewer.display_pdf(next_pdf)
                
                # Clear filters
                for frame in self.filter_frames:
                    frame["fuzzy"].clear()
                
                # Load first filter values
                self._load_filter_values()
                
                self._update_status("Ready")
            else:
                self.current_pdf = None
                self.current_pdf_start_time = None
                self.pdf_viewer.display_pdf(None)
                self._update_status("No files to process")
            
            # Update process button state
            self._update_process_button()
            
        except Exception as e:
            self._handle_error(e, "loading next PDF")
    
    def _update_process_button(self) -> None:
        """Update the state of the process button."""
        enabled = (
            self.current_pdf is not None
            and all(frame["fuzzy"].get() for frame in self.filter_frames)
        )
        self.process_button.setEnabled(enabled)
    
    def _update_display(self) -> None:
        """Update the queue display."""
        self.queue_display.update_display(self.processing_thread.tasks)
    
    def _clear_completed(self) -> None:
        """Clear completed tasks from the queue."""
        self.processing_thread.tasks = {
            k: v for k, v in self.processing_thread.tasks.items()
            if v.status != "completed"
        }
    
    def _retry_failed(self) -> None:
        """Retry failed tasks."""
        for task in self.processing_thread.tasks.values():
            if task.status == "failed":
                task.status = "pending"
                task.error_msg = ""
    
    def _on_task_completed(self, task_id: str, status: str) -> None:
        """Handle task completion."""
        if task_id in self.processing_thread.tasks:
            task = self.processing_thread.tasks[task_id]
            task.status = status
            task.end_time = datetime.now()
            
            # If task is completed successfully, mark as processed but don't reload current PDF
            if status == "completed":
                print(f"[DEBUG] Task completed successfully: {task_id}")
                
                # Mark the source file as processed in our tracking system
                # This ensures we won't pick it up again even if it's not deleted
                if task.pdf_path:
                    # Also track the original location if different
                    paths_to_mark = {task.pdf_path}
                    
                    if task.original_pdf_location and not self.pdf_manager._paths_equal(
                            task.original_pdf_location, task.pdf_path):
                        paths_to_mark.add(task.original_pdf_location)
                    
                    # Mark all unique paths as processed
                    for path in paths_to_mark:
                        self.pdf_manager.mark_file_processed(path)
                        print(f"[DEBUG] Marked as processed: {os.path.basename(path)}")
                
                # Process events to ensure any pending database writes or file operations complete
                QApplication.processEvents()
                
                # Only load next PDF if the current one is gone or was the one that just finished
                if (not self.current_pdf) or (self.current_pdf and task.pdf_path and 
                                           self.pdf_manager._paths_equal(self.current_pdf, task.pdf_path)):
                    print(f"[DEBUG] Loading next PDF after task completion (current PDF is {self.current_pdf})")
                    # Use a timer to load the next PDF after a brief delay
                    QTimer.singleShot(1000, self._load_next_pdf)
                else:
                    print(f"[DEBUG] Keeping current PDF displayed: {os.path.basename(self.current_pdf)}")
                    
                    # Just update the process button state without reloading
                    self._update_process_button()
    
    def _on_task_failed(self, task_id: str, error_msg: str) -> None:
        """Handle task failure."""
        if task_id in self.processing_thread.tasks:
            task = self.processing_thread.tasks[task_id]
            task.status = "failed"
            task.error_msg = error_msg
            task.end_time = datetime.now()
    
    def _on_config_change(self) -> None:
        """Handle configuration changes."""
        # Cancel any pending operation
        if self._pending_config_change_id is not None:
            self._update_timer.stop()
            self._pending_config_change_id = None
        
        # Schedule the change
        self._pending_config_change_id = self._update_timer.singleShot(
            250,  # 250ms delay
            self._apply_config_change
        )
    
    def _apply_config_change(self) -> None:
        """Apply configuration changes."""
        self._pending_config_change_id = None
        self._setup_filters()
        self._load_next_pdf()
    
    def closeEvent(self, event: Any) -> None:
        """Handle tab closure."""
        self.processing_thread.stop()
        super().closeEvent(event)