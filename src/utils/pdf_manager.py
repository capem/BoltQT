from __future__ import annotations

import gc
import os
import re
import shutil
import time
import traceback
from datetime import datetime
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional

from .logger import get_logger
from .models import PDFTask
from .path_utils import is_same_path, normalize_path
from .template_manager import TemplateManager


class PDFManager:
    """Manages PDF file operations."""

    def __init__(self) -> None:
        """Initialize PDFManager."""
        self._current_path: Optional[str] = None
        self.template_manager = TemplateManager()
        # Set to track processed files
        self._processed_files = set()
        self._viewer_ref = None

    def _normalize_path(self, path: str) -> str:
        """Normalize a path for consistent comparison.

        Args:
            path: The path to normalize

        Returns:
            str: The normalized path
        """
        # Use the centralized normalize_path function from path_utils
        return normalize_path(path)

    def _paths_equal(self, path1: str, path2: str) -> bool:
        """Check if two paths point to the same file.

        Args:
            path1: First path
            path2: Second path

        Returns:
            bool: True if the paths point to the same file
        """
        # Use the centralized is_same_path function from path_utils
        return is_same_path(path1, path2)

    def get_next_pdf(
        self, source_folder: str, active_tasks: Dict[str, PDFTask]
    ) -> Optional[str]:
        """Get the next available PDF file from the source folder.

        Args:
            source_folder: Path to the folder containing PDF files.
            active_tasks: Dictionary of active tasks, keyed by PDF path.

        Returns:
            Optional[str]: Path to the next available PDF file, or None if no files are available.
        """
        try:
            if not os.path.exists(source_folder):
                return None

            logger = get_logger()

            # Print active tasks for debugging
            if active_tasks:
                logger.debug(f"Current active tasks: {len(active_tasks)}")
                for task_id, task in active_tasks.items():
                    logger.debug(
                        f"Task {task_id[:8]}... status: {task.status}, file: {os.path.basename(task.pdf_path)}"
                    )
            else:
                logger.debug("No active tasks")

            # Get all PDF files in the folder
            all_files = [
                f for f in os.listdir(source_folder) if f.lower().endswith(".pdf")
            ]
            logger.debug(f"Found {len(all_files)} total PDF files in source folder")

            # Track how many files we're skipping and why
            skipped_processed = 0
            skipped_active = 0
            skipped_locked = 0

            pdf_files = []
            for file in all_files:
                # Skip files marked as processed with the .processed suffix
                if file.lower().endswith(".processed.pdf"):
                    skipped_processed += 1
                    continue

                if file.lower().endswith(".pdf"):
                    full_path = os.path.join(source_folder, file)

                    # Check if this file is in our processed files list
                    is_processed = False
                    for processed_file in self._processed_files:
                        if self._paths_equal(full_path, processed_file):
                            logger.debug(f"Skipping previously processed file: {file}")
                            is_processed = True
                            skipped_processed += 1
                            break

                    if is_processed:
                        continue

                    # Check if the file is in active tasks
                    in_active_tasks = False
                    for path in active_tasks:
                        if self._paths_equal(full_path, path):
                            in_active_tasks = True
                            skipped_active += 1
                            break

                    if in_active_tasks:
                        continue

                    # Check if the file is being processed in any task
                    is_in_processing = False
                    task_ids_with_path = []
                    for task_id, task in active_tasks.items():
                        if self._paths_equal(
                            full_path, task.pdf_path
                        ) or self._paths_equal(full_path, task.original_pdf_location):
                            task_ids_with_path.append(task_id)
                            is_in_processing = True

                    if is_in_processing:
                        logger.debug(
                            f"Skipping file that is being processed in tasks: {task_ids_with_path}"
                        )
                        skipped_active += 1
                        continue

                    # Skip files that are already in use by checking if they can be opened
                    try:
                        # Use a quick try-except to test if the file can be opened
                        with open(full_path, "rb") as _:
                            # Just try to open the file to check if it's accessible
                            pass
                        # If we got here, the file can be opened
                        pdf_files.append(full_path)
                    except PermissionError:
                        # Skip this file as it's locked by another process
                        logger.debug(f"Skipping locked file: {file}")
                        skipped_locked += 1
                        continue

            # Print summary of what we found
            logger.debug(
                f"PDF selection summary: {len(pdf_files)} available, {skipped_processed} skipped (processed), {skipped_active} skipped (active tasks), {skipped_locked} skipped (locked)"
            )

            if not pdf_files:
                return None

            # Return the first available file
            selected_file = sorted(pdf_files)[0]
            logger.info(f"Selected next PDF file: {selected_file}")
            return selected_file

        except Exception as e:
            logger.error(f"Error getting next PDF: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def close_current_pdf(self) -> None:
        """Clear the currently tracked PDF."""
        # Simply clear the path reference
        if self._current_path:
            logger = get_logger()
            logger.debug(f"Stopped tracking PDF: {self._current_path}")
            self._current_path = None

    def generate_output_path(self, template: str, data: Dict[str, Any]) -> str:
        """Generate output path based on template and data.

        Args:
            template: Path template string.
            data: Dictionary of data for template substitution.

        Returns:
            str: Generated output path.
        """
        logger = get_logger()
        try:
            logger.debug(f"Generating output path with template: '{template}'")
            logger.debug(f"Template data keys: {sorted(data.keys())}")

            # Create a copy of the data to avoid modifying the original
            template_data = data.copy()

            # Clean Excel Row information from all string values
            for key in list(template_data.keys()):
                if isinstance(template_data[key], str):
                    # Remove Excel Row information from the value
                    template_data[key] = re.sub(
                        r"\s*⟨Excel Row[:-]\s*\d+⟩", "", template_data[key]
                    )

            # Handle NaT values and convert dates
            for key in list(template_data.keys()):
                # Check for NaT values from pandas
                if (
                    hasattr(template_data[key], "isnull")
                    and template_data[key].isnull()
                ):
                    logger.debug(f"Found NaT value for {key}, using fallback")
                    template_data[key] = "unknown_date"
                    # Also add a fallback datetime
                    template_data[f"{key}_date"] = datetime.now()

                # For any datetime values, ensure we have a _date suffixed version too
                if isinstance(template_data[key], datetime):
                    template_data[f"{key}_date"] = template_data[key]

                # Log important keys
                if key in ["processed_folder", "filter1", "filter2", "filter3"]:
                    value_type = type(template_data[key]).__name__
                    value_str = str(template_data[key])
                    logger.debug(
                        f"Template data['{key}']: {value_str} (type: {value_type})"
                    )

            # Let the template manager handle the formatting with the improved implementation
            try:
                # Log the template and data before processing
                logger.debug(f"Calling template_manager.format_path with template: '{template}'")
                logger.debug(f"Template data contains {len(template_data)} keys")

                # The updated template manager now handles both curly brace and ${} formats
                result = self.template_manager.format_path(template, template_data)
                logger.debug(f"Generated path: {result}")

                # If we still have unresolved template variables after processing
                if ("{" in result and "}" in result) or (
                    "${" in result and "}" in result
                ):
                    logger.warning(
                        f"Output path still has unresolved variables: {result}"
                    )
                    # Try basic substitution for any remaining variables
                    original_result = result
                    result = re.sub(r"\{[^}]+\}", "_", result)
                    result = re.sub(r"\$\{[^}]+\}", "_", result)
                    logger.debug(f"Cleaned path from '{original_result}' to '{result}'")
            except Exception as e:
                logger.error(f"Template manager error: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Fallback path with timestamp
                result = os.path.join(
                    template_data.get("processed_folder", "processed"),
                    f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                )

            # Normalize path separators using path_utils
            result = normalize_path(result)

            return result
        except Exception as e:
            logger.error(f"Error generating output path: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return a fallback path to avoid complete failure
            return os.path.join(
                data.get("processed_folder", "processed"),
                f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            )

    def mark_file_processed(self, file_path: str) -> None:
        """Mark a file as processed even if it couldn't be deleted.

        Args:
            file_path: Path to the file that has been processed
        """
        if file_path:
            logger = get_logger()
            normalized_path = self._normalize_path(file_path)
            self._processed_files.add(normalized_path)
            logger.debug(
                f"Marked file as processed (internal tracking): {normalized_path}"
            )

            # Log the full list for debugging
            logger.debug(
                f"Current processed files count: {len(self._processed_files)}"
            )

            # Immediately update our memory of processed files
            # This ensures future get_next_pdf calls will respect this newly processed file
            gc.collect()

    def process_pdf(
        self,
        task: PDFTask,
        template_data: Dict[str, Any],
        processed_folder: str,
        output_template: str,
    ) -> None:
        """Process a PDF file according to the task specifications.

        Args:
            task: PDFTask object containing processing details.
            template_data: Dictionary of data for path generation.
            processed_folder: Base folder for processed files.
            output_template: Template string for output path generation.
        """
        logger = get_logger()
        # Normalize the source path using path_utils
        source_path = normalize_path(task.pdf_path)
        logger.info(f"Processing PDF file: {source_path}")

        if not os.path.exists(source_path):
            logger.error(f"PDF file not found: {source_path}")
            raise FileNotFoundError(f"PDF file not found: {source_path}")

        # Store original location for potential revert operation
        task.original_pdf_location = source_path

        # Ensure file is not locked and accessible
        if not self._ensure_file_released(source_path):
            raise ValueError(
                f"Could not access file: {source_path} (file may be locked)"
            )

        # Create temporary directory for atomic operations
        with TemporaryDirectory() as temp_dir:
            try:
                # Generate output path
                output_path = self.generate_output_path(output_template, template_data)
                if not output_path:
                    raise ValueError("Failed to generate output path")

                # Make the output path absolute
                if not os.path.isabs(output_path):
                    output_path = os.path.join(processed_folder, output_path)

                # Normalize output path using path_utils
                output_path = normalize_path(output_path)
                logger.debug(f"Final output path: {output_path}")

                # Ensure output directory exists
                try:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    logger.debug(
                        f"Created output directory: {os.path.dirname(output_path)}"
                    )
                except Exception as e:
                    logger.error(f"Error creating output directory: {str(e)}")
                    raise ValueError(f"Could not create output directory: {str(e)}")

                # Copy PDF to temporary location
                temp_pdf = os.path.join(temp_dir, "temp.pdf")
                try:
                    shutil.copy2(source_path, temp_pdf)
                    logger.debug(f"Copied PDF to temporary location: {temp_pdf}")
                except Exception as e:
                    logger.error(f"Error copying PDF to temp location: {str(e)}")
                    raise ValueError(
                        f"Could not copy PDF to temporary location: {str(e)}"
                    )

                # Create a new document for rotation if needed
                if task.rotation_angle != 0:
                    try:
                        # Store rotation in task metadata for viewer
                        task.metadata = {"rotation": task.rotation_angle}
                        logger.debug(
                            f"Stored rotation of {task.rotation_angle} degrees in metadata"
                        )
                    except Exception as e:
                        logger.warning(f"Error storing rotation metadata: {str(e)}")
                        # Continue even if metadata storage fails

                # Move to final location with versioning
                try:
                    # Use our versioning method to handle existing files
                    final_path, old_path = self.move_pdf_with_versioning(source_path, output_path, task)
                    logger.info(
                        f"Successfully moved PDF to final location: {final_path}"
                    )

                    # Set the processed location in the task
                    task.processed_pdf_location = final_path

                    # Log if an old file was created
                    if old_path:
                        logger.debug(f"Old version of file stored at: {old_path}")

                    # Remove the original file from the source folder
                    try:
                        # Try to remove with retries
                        if self._remove_file_with_retry(source_path):
                            logger.debug(
                                "Successfully removed or renamed the original file."
                            )
                        else:
                            # If removal failed, mark the file as processed in our tracking
                            self.mark_file_processed(source_path)
                    except Exception as e:
                        logger.warning(
                            f"Could not remove original PDF: {str(e)}"
                        )
                        # Mark the file as processed even if removal failed
                        self.mark_file_processed(source_path)

                    logger.info("PDF processing completed successfully")
                except Exception as e:
                    logger.error(f"Error moving PDF to final location: {str(e)}")
                    raise ValueError(f"Could not move PDF to final location: {str(e)}")

            except Exception as e:
                logger.error(f"Error processing PDF: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise

    def _remove_file_with_retry(
        self, file_path: str, max_attempts: int = 3, delay: float = 0.5
    ) -> bool:
        """Remove a file with retry logic in case it's locked.

        Args:
            file_path: Path to the file to remove
            max_attempts: Maximum number of removal attempts
            delay: Delay between attempts in seconds

        Returns:
            bool: True if successful, False otherwise

        Raises:
            Exception: If all attempts fail
        """
        logger = get_logger()
        for attempt in range(max_attempts):
            try:
                os.remove(file_path)
                logger.debug(f"Removed original PDF from source folder: {file_path}")
                return True
            except Exception as e:
                logger.warning(
                    f"Removal attempt {attempt + 1} failed: {str(e)}, retrying in {delay}s..."
                )
                time.sleep(delay)
        logger.error(f"Failed to remove file after {max_attempts} attempts: {file_path}")
        return False

    def revert_pdf_location(self, task: PDFTask) -> bool:
        """Revert a PDF to its original location.

        Args:
            task: PDFTask object containing processing details.

        Returns:
            bool: True if successful, False otherwise.
        """
        logger = get_logger()
        try:
            if (
                not task
                or not task.processed_pdf_location
                or not task.original_pdf_location
            ):
                logger.warning("Cannot revert: missing required task information")
                return False

            if not os.path.exists(task.processed_pdf_location):
                logger.warning(f"Processed PDF not found: {task.processed_pdf_location}")
                return False

            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(task.original_pdf_location), exist_ok=True)

            # Move the file back to its original location
            shutil.move(task.processed_pdf_location, task.original_pdf_location)
            logger.info(
                f"Reverted PDF from {task.processed_pdf_location} to {task.original_pdf_location}"
            )

            # Check if we have a versioned file path stored in the task
            if hasattr(task, 'versioned_pdf_path') and task.versioned_pdf_path:
                versioned_path = task.versioned_pdf_path
                if os.path.exists(versioned_path):
                    try:
                        # Restore the old file to its original name (without the "old_" prefix)
                        shutil.move(versioned_path, task.processed_pdf_location)
                        logger.info(
                            f"Restored original file from {versioned_path} to {task.processed_pdf_location}"
                        )
                    except Exception as restore_error:
                        logger.warning(f"Could not restore original file: {str(restore_error)}")
                        # Continue even if restoration fails - the revert operation itself succeeded
                else:
                    logger.debug(f"Versioned file not found: {versioned_path}")

            return True

        except Exception as e:
            logger.error(f"Error reverting PDF: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def move_pdf_with_versioning(self, source_path: str, target_path: str, task=None) -> tuple:
        """Move a PDF file to a target path, handling existing files by versioning.

        If a file already exists at the target path, it will be renamed with an 'old_' prefix
        and a timestamp before the new file is moved to the target location.
        This allows for maintaining multiple versions of the same file.

        Args:
            source_path: Path to the source PDF file
            target_path: Destination path where the file should be moved
            task: Optional PDFTask object to store the versioned file path

        Returns:
            tuple: (final_path, old_path) where:
                - final_path is the path where the file was moved
                - old_path is the path of the renamed file (or None if no file was renamed)

        Raises:
            FileNotFoundError: If the source file doesn't exist
            ValueError: If the file cannot be moved
        """
        logger = get_logger()
        old_path = None
        try:
            # Normalize paths
            source_path = normalize_path(source_path)
            target_path = normalize_path(target_path)

            # Check if source file exists
            if not os.path.exists(source_path):
                logger.error(f"Source file not found: {source_path}")
                raise FileNotFoundError(f"Source file not found: {source_path}")

            # Ensure target directory exists
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # Check if target file already exists
            if os.path.exists(target_path):
                logger.debug(f"Target file already exists: {target_path}")

                # Get directory and filename components
                target_dir = os.path.dirname(target_path)
                target_filename = os.path.basename(target_path)

                # Get file name and extension separately
                filename_parts = os.path.splitext(target_filename)
                base_name = filename_parts[0]
                extension = filename_parts[1] if len(filename_parts) > 1 else ""

                # Create versioned filename with 'old_' prefix and timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                old_filename = f"old_{timestamp}_{base_name}{extension}"
                old_path = os.path.join(target_dir, old_filename)

                # Rename the existing file - with timestamp, we don't need to check for existing old versions
                try:
                    shutil.move(target_path, old_path)
                    logger.debug(f"Renamed existing file to: {old_path}")

                    # Store the versioned file path in the task if provided
                    if task and hasattr(task, 'versioned_pdf_path'):
                        task.versioned_pdf_path = old_path
                        logger.debug(f"Stored versioned file path in task: {old_path}")
                except Exception as e:
                    logger.warning(f"Error renaming existing file: {str(e)}")
                    old_path = None
                    # Continue anyway - we'll try to copy the new file

            # Copy the new file to the target location
            shutil.copy2(source_path, target_path)
            logger.debug(f"Successfully copied file to: {target_path}")

            return target_path, old_path

        except Exception as e:
            logger.error(f"Error in move_pdf_with_versioning: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise ValueError(f"Failed to move PDF file: {str(e)}")

    def _ensure_file_released(self, file_path: str, max_attempts: int = 3) -> bool:
        """Check if a file is accessible and not locked.

        Args:
            file_path: Path to the file to check
            max_attempts: Maximum number of attempts to check file accessibility

        Returns:
            bool: True if file is accessible, False otherwise
        """


        # If this is the current tracked file, stop tracking it
        if self._paths_equal(file_path, self._current_path):
            self.close_current_pdf()

        logger = get_logger()
        # Try to verify file is accessible
        for attempt in range(max_attempts):
            try:
                # First try to check if the file exists
                if not os.path.exists(file_path):
                    logger.debug(f"File does not exist: {file_path}")
                    return True  # Consider non-existent files as "released"

                # Try to open the file to check if it's accessible
                with open(file_path, "rb") as _:
                    logger.debug(f"Verified file is accessible: {file_path}")
                    return True
            except PermissionError:
                if attempt < max_attempts - 1:
                    logger.debug(f"File locked, retry {attempt + 1}: {file_path}")
                    time.sleep(0.5)  # Short delay between retries
                    continue
                logger.warning(
                    f"File inaccessible after {max_attempts} attempts: {file_path}"
                )
                return False
            except FileNotFoundError:
                logger.debug(f"File does not exist: {file_path}")
                return True  # Consider non-existent files as "released"
            except Exception as e:
                logger.error(f"Error checking file: {str(e)}")
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
                    continue
                return False

        return False

    def move_skipped_pdf_to_folder(self, source_path: str, skip_folder: str) -> Optional[str]:
        """Moves a skipped PDF to the skip folder with timestamping, handling potential locks and retrying.

        Uses a copy-then-delete approach for potentially better cross-device compatibility.

        Args:
            source_path: Path to the source PDF file.
            skip_folder: Destination folder for skipped files.

        Returns:
            The path to the moved file in the skip folder if successful.
            None if the operation failed due to invalid input, file locks,
            or errors during copy/delete after retries.
        """
        logger = get_logger()
        # --- 1. Input Validation ---
        if not source_path or not os.path.isfile(source_path):
            logger.warning(f"Invalid or missing source file: {source_path}")
            return None
        if not skip_folder:
            logger.warning("Missing skip folder path.")
            return None

        # --- 2. Ensure File is Released ---
        # Attempts to ensure the file is not locked before proceeding.
        if not self._ensure_file_released(source_path, max_attempts=5):
            logger.warning(f"File appears locked after checks, cannot move: {source_path}")
            return None # Cannot proceed if file is locked

        # --- 3. Prepare Target Path ---
        try:
            # Ensure the destination directory exists.
            os.makedirs(skip_folder, exist_ok=True)

            # Construct the new filename with a timestamp.
            base_name = os.path.basename(source_path)
            name, ext = os.path.splitext(base_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Creates a unique name like 'original_skipped_20230101_120000.pdf'
            target_path = os.path.join(skip_folder, f"{name}_skipped_{timestamp}{ext}")

        except Exception as path_e:
            # Handle potential errors during path creation (e.g., permissions).
            logger.error(f"Error preparing target path or directory: {str(path_e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

        # --- 4. Attempt Copy and Delete with Retries ---
        max_attempts = 3
        for attempt in range(max_attempts):
            copied = False
            try:
                # --- 4a. Copy File ---
                logger.debug(f"Attempt {attempt + 1}/{max_attempts}: Copying '{source_path}' to '{target_path}'")
                shutil.copy2(source_path, target_path) # copy2 preserves metadata
                copied = True
                logger.debug("Copy successful.")

                # --- 4b. Delete Original File ---
                logger.debug(f"Attempt {attempt + 1}/{max_attempts}: Removing original file '{source_path}'")
                os.remove(source_path)
                logger.debug("Original file removed successfully.")

                # --- Success Case ---
                # If both copy and delete succeed, mark the *new* file as processed and return its path.
                self.mark_file_processed(target_path)
                logger.info(f"Successfully moved skipped PDF to: {target_path}")
                return target_path # Operation complete

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {str(e)}")

                # --- Cleanup on Failure ---
                # If copy succeeded but delete failed, try to remove the copied file to avoid duplicates.
                if copied and os.path.exists(target_path):
                    try:
                        logger.debug(f"Deletion of original failed, cleaning up copied file: {target_path}")
                        os.remove(target_path)
                        logger.debug("Cleanup successful.")
                    except Exception as cleanup_e:
                        # Log if cleanup fails, but proceed to retry/fail the main operation.
                        logger.warning(f"Failed to clean up copied file '{target_path}' after error: {str(cleanup_e)}")

                # --- Retry Logic ---
                if attempt < max_attempts - 1:
                    logger.debug("Retrying in 0.5 seconds...")
                    time.sleep(0.5)
                    # Loop continues to the next attempt
                else:
                    # All attempts failed.
                    logger.error(f"Failed to move file '{source_path}' after {max_attempts} attempts.")
                    return None # Exit after last attempt