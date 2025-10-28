from __future__ import annotations

import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal

from .config_manager import ConfigManager
from .excel_manager import ExcelManager
from .logger import get_logger
from .models import PDFTask
from .pdf_manager import PDFManager
from .performance_profiler import PerformanceProfiler


class ProcessingThread(QThread):
    """Background thread for processing PDFs."""

    task_completed = pyqtSignal(str, str)  # task_id, status
    task_failed = pyqtSignal(str, str)  # task_id, error_message
    task_started = pyqtSignal(str)  # task_id

    def __init__(
        self,
        config_manager: ConfigManager,
        excel_manager: ExcelManager,
        pdf_manager: PDFManager,
    ) -> None:
        super().__init__()

        # Store manager references
        self.config_manager = config_manager
        self.excel_manager = excel_manager
        self.pdf_manager = pdf_manager

        # Initialize state
        self.tasks: Dict[str, PDFTask] = {}
        self.running = True

        # Cache for Excel data
        self._excel_data_cache = {
            "file": None,
            "sheet": None,
            "data": None,
            "columns": None,
        }

        # Performance profiler
        self._profiler = PerformanceProfiler()

    def run(self) -> None:
        """Process tasks in the queue."""
        logger = get_logger()
        logger.info("Starting PDF processing thread")

        while self.running:
            task_to_process, task_id = self._get_next_pending_task()

            if task_to_process:
                self._process_task(task_to_process, task_id)
            else:
                time.sleep(0.1)

    def _process_task(self, task: PDFTask, task_id: str) -> None:
        """Process a single PDF task."""
        logger = get_logger()
        logger.info(f"Processing task {task_id}: {task.pdf_path}")
        self._profiler.start_operation(f"process_task_{task_id}")

        try:
            config = self._prepare_and_validate_config()
            row_idx, row_data, filter_columns, filter_values = self._get_or_create_excel_row(task, config)
            task.row_idx = row_idx

            template_data = self._create_template_data(row_data, filter_columns, filter_values, row_idx)
            template_data["processed_folder"] = config["processed_folder"]

            self._handle_pdf_and_hyperlink(task, config, row_idx, template_data, filter_columns)

            task.status = "completed"
            task.end_time = datetime.now()
            self.task_completed.emit(task_id, "completed")
            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Task processing error: {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            if task_id in self.tasks:
                self.tasks[task_id].status = "failed"
                self.tasks[task_id].error_msg = error_msg
                self.tasks[task_id].end_time = datetime.now()
            self.task_failed.emit(task_id, error_msg)
            logger.error(f"Task {task_id} failed: {error_msg}")

        finally:
            self._profiler.end_operation(f"process_task_{task_id}")
            self.excel_manager.clear_workbook_cache()
            time.sleep(0.05)

    def _prepare_and_validate_config(self) -> Dict[str, Any]:
        """Prepare and validate the configuration for processing."""
        self._profiler.start_operation("setup_and_validation")
        config = self.config_manager.get_config()
        self._validate_config(config)
        self._profiler.end_operation("setup_and_validation")
        return config

    def _get_or_create_excel_row(self, task: PDFTask, config: Dict[str, Any]) -> tuple:
        """Get or create the relevant row in the Excel file."""
        self._profiler.start_operation("excel_data_operations")
        self._ensure_excel_data_loaded(config)
        df = self._excel_data_cache["data"]

        filter_columns = self._get_filter_columns(config, task.filter_values)
        filter_values = task.filter_values.copy()

        row_idx = self._find_matching_row(df, filter_columns, filter_values, task)
        
        # Refresh DataFrame cache if a new row was added
        if task.created_new_row:
            self._excel_data_cache["data"] = self.excel_manager.excel_data
            df = self._excel_data_cache["data"]

        if row_idx >= len(df):
            raise IndexError(f"Row index {row_idx} is out of bounds (df length: {len(df)})")
            
        row_data = df.iloc[row_idx]
        self._profiler.end_operation("excel_data_operations")
        
        return row_idx, row_data, filter_columns, filter_values

    def _handle_pdf_and_hyperlink(self, task: PDFTask, config: Dict[str, Any], row_idx: int, template_data: Dict[str, Any], filter_columns: List[str]) -> None:
        """Handle PDF processing and Excel hyperlink updates."""
        processed_path = self.pdf_manager.generate_output_path(config["output_template"], template_data)
        hyperlink_config = config.get("hyperlink_mode", {})
        standard_mode = hyperlink_config.get("standard", True)
        enhanced_mode = hyperlink_config.get("enhanced", False)
        original_link = None

        try:
            if enhanced_mode:
                self._profiler.start_operation("enhanced_hyperlink_mode")
                self._update_row_with_filter_data(row_idx, filter_columns, task.filter_values, task, config)
                filter_column = filter_columns[1] if len(filter_columns) > 1 else None
                original_link = self.excel_manager.update_pdf_link(config["excel_file"], config["excel_sheet"], row_idx, processed_path, filter_column)
                self._profiler.end_operation("enhanced_hyperlink_mode")
            elif standard_mode:
                self._profiler.start_operation("standard_hyperlink_mode")
                filter_column = filter_columns[1] if len(filter_columns) > 1 else None
                original_link = self.excel_manager.update_pdf_link(config["excel_file"], config["excel_sheet"], row_idx, processed_path, filter_column)
                self._profiler.end_operation("standard_hyperlink_mode")

            task.original_excel_hyperlink = original_link
            task.processed_pdf_location = processed_path
            get_logger().info(f"Excel hyperlink processing completed, original: {original_link}")

        except Exception as e:
            get_logger().warning(f"Excel hyperlink processing failed: {str(e)}")

        self.pdf_manager.process_pdf(
            task=task,
            template_data=template_data,
            processed_folder=config["processed_folder"],
            output_template=config["output_template"],
        )

    def _update_row_with_filter_data(
        self,
        row_idx: int,
        filter_columns: List[str],
        filter_values: List[str],
        task: PDFTask,
        config: Dict[str, Any],
    ) -> None:
        """Update Excel row with filter data in enhanced mode.
        
        Args:
            row_idx: Excel row index (0-based)
            filter_columns: List of filter column names
            filter_values: List of filter values to update
            task: The current PDF task
            config: The current configuration
        """
        logger = get_logger()
        try:
            logger.debug(f"Updating row {row_idx} with filter data in enhanced mode")
            
            # Update row data with filter information
            # This ensures that even if the row was created with incomplete data,
            # it gets populated with the full filter values
            self.excel_manager.update_row_data(
                config["excel_file"],
                config["excel_sheet"],
                row_idx,
                filter_columns,
                filter_values,
            )
            
            # Refresh the cached Excel data to reflect changes
            self._excel_data_cache["data"] = self.excel_manager.excel_data
            
            logger.info(f"Successfully updated row {row_idx} with filter data")
            
        except Exception as e:
            logger.warning(f"Row data update failed in enhanced mode: {str(e)}")
            # Don't fail the entire process if row update fails
            # The hyperlink update should still proceed

    def _get_next_pending_task(self):
        """Find the next pending task in the queue."""
        for task_id, task in self.tasks.items():
            if task.status == "pending":
                task.status = "processing"
                # Emit signal to notify UI that task has started
                self.task_started.emit(task_id)
                return task, task_id
        return None, None

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate that all required configurations are present."""
        required_configs = [
            "processed_folder",
            "output_template",
            "excel_file",
            "excel_sheet",
        ]
        missing_configs = [cfg for cfg in required_configs if not config.get(cfg)]
        if missing_configs:
            raise Exception(
                f"Missing required configuration: {', '.join(missing_configs)}"
            )

    def _ensure_excel_data_loaded(self, config: Dict[str, Any]) -> None:
        """Ensure Excel data is loaded, using cache if possible."""
        excel_file = config["excel_file"]
        excel_sheet = config["excel_sheet"]

        # Check if we need to reload the data
        if (
            self._excel_data_cache["file"] != excel_file
            or self._excel_data_cache["sheet"] != excel_sheet
            or self._excel_data_cache["data"] is None
        ):
            # Load new data
            self.excel_manager.load_excel_data(excel_file, excel_sheet)

            # Update cache
            self._excel_data_cache["file"] = excel_file
            self._excel_data_cache["sheet"] = excel_sheet
            self._excel_data_cache["data"] = self.excel_manager.excel_data

            # Pre-convert all string columns to strings to avoid repeated conversions
            for col in self._excel_data_cache["data"].select_dtypes(
                exclude=["datetime64"]
            ):
                self._excel_data_cache["data"][col] = self._excel_data_cache["data"][
                    col
                ].astype(str)

    def _get_filter_columns(
        self, config: Dict[str, Any], filter_values: List[str]
    ) -> List[str]:
        """Get filter columns from the configuration."""
        if "filter_columns" not in config or not isinstance(
            config["filter_columns"], list
        ):
            raise Exception("Missing or invalid 'filter_columns' in configuration.")

        num_filters = len(filter_values)
        config_columns = config["filter_columns"]

        if len(config_columns) < num_filters:
            raise Exception(
                f"Configuration provides {len(config_columns)} filter columns, "
                f"but {num_filters} filter values were given."
            )

        return config_columns[:num_filters]

    def _create_new_row(
        self, filter_columns: List[str], filter_values: List[str], task: Optional[PDFTask] = None
    ) -> int:
        """Create a new Excel row with the given filter values."""
        logger = get_logger()
        config = self.config_manager.get_config()

        # Create a new row using the excel manager
        logger.debug(f"Adding new row to Excel with filter values: {filter_values}")
        _, new_row_idx = self.excel_manager.add_new_row(
            config["excel_file"],
            config["excel_sheet"],
            filter_columns,
            filter_values,
            create_backup=False,  # Skip backup for performance
        )

        # Update the cached DataFrame
        self._excel_data_cache["data"] = self.excel_manager.excel_data

        # Mark the task as having created a new row
        if task:
            task.created_new_row = True
            logger.debug(f"Marked task {task.task_id} as having created a new row")

        filter2_value = filter_values[1] if len(filter_values) > 1 else "N/A"
        logger.info(f"Added new row {new_row_idx} (Excel row {new_row_idx + 2}) for filter2 value '{filter2_value}'")
        return new_row_idx

    def _find_matching_row(
        self,
        df: pd.DataFrame,
        filter_columns: List[str],
        filter_values: List[str],
        task: Optional[PDFTask] = None,
    ) -> int:
        """Find or create a matching row in Excel data."""
        logger = get_logger()

        # Trust task.row_idx if valid bounds
        if task and task.row_idx >= 0 and task.row_idx < len(df):
            logger.debug(f"Using task row_idx {task.row_idx} (Excel row {task.row_idx + 2})")
            return task.row_idx
        else:
            # Create new row with clean filter2 value
            logger.debug(f"Creating new row for filter values: {filter_values}")
            return self._create_new_row(filter_columns, filter_values, task)

    def _create_template_data(
        self,
        row_data: pd.Series,
        filter_columns: List[str],
        filter_values: List[str],
        row_idx: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create template data dictionary from row data and filter values."""
        template_data = {}
        date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]

        # Add filter values to template data
        for i, (column, value) in enumerate(zip(filter_columns, filter_values), 1):
            # For filter2, include Excel row in the value only if it's not already there
            if i == 2 and row_idx is not None:
                import re

                if not re.search(r"⟨Excel Row[:-]\s*\d+⟩", value):
                    excel_row = row_idx + 2  # Convert to Excel row (1-based + header)
                    formatted_value = value + f" ⟨Excel Row: {excel_row}⟩"
                    template_data[f"filter{i}"] = formatted_value
                else:
                    # Use value as is if it already has Excel Row info
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
                        get_logger().debug(f"Converted filter{i} to datetime: {date_obj}")
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
                            get_logger().debug(f"Converted {column} to datetime")
                            break
                        except ValueError:
                            continue
                elif isinstance(value, pd.Timestamp):
                    # Convert pandas Timestamp to Python datetime
                    template_data[f"{column}_date"] = value.to_pydatetime()
                    get_logger().debug(f"Converted pandas Timestamp {column} to datetime")

        # Add the current date and time
        template_data["current_date"] = datetime.now()

        get_logger().debug(f"Created template data with {len(template_data)} keys")
        return template_data

    def stop(self) -> None:
        """Stop the processing thread."""
        logger = get_logger()
        logger.info("Stopping PDF processing thread")
        self.running = False
        self.wait()

    def print_performance_stats(self) -> None:
        """Print performance statistics for debugging."""
        self._profiler.print_summary()
