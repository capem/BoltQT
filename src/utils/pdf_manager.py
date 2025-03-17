from __future__ import annotations
from typing import Dict, Any, Optional
import os
from tempfile import TemporaryDirectory
import shutil
from PyQt6.QtCore import QObject
from PyQt6.QtPdf import QPdfDocument
from .models import PDFTask
from .template_manager import TemplateManager
from datetime import datetime


class PDFManager(QObject):
    """Manages PDF file operations."""

    def __init__(self) -> None:
        """Initialize PDFManager."""
        super().__init__()
        self._current_doc: Optional[QPdfDocument] = None
        self._current_path: Optional[str] = None
        self._rotation: int = 0
        self.template_manager = TemplateManager()
        # Set to track processed files that couldn't be deleted
        self._processed_files = set()

    def _normalize_path(self, path: str) -> str:
        """Normalize a path for consistent comparison.

        Args:
            path: The path to normalize

        Returns:
            str: The normalized path
        """
        if not path:
            return ""

        # Replace both forward and backslashes with the system's path separator
        normalized = path.replace("/", os.path.sep).replace("\\", os.path.sep)

        # Handle UNC paths (network paths)
        # Convert //server/share to \\server\share or vice versa based on the OS
        if normalized.startswith(os.path.sep + os.path.sep):
            # It's already in the form \\server\share or //server/share
            pass
        elif normalized.startswith(r"\\"):
            # It's in Windows UNC format but we're on a system using forward slashes
            if os.path.sep == "/":
                normalized = normalized.replace(r"\\", "//")
        elif normalized.startswith("//"):
            # It's in Unix UNC format but we're on a system using backslashes
            if os.path.sep == "\\":
                normalized = normalized.replace("//", r"\\")

        # For case-insensitive file systems, convert to lowercase
        if os.name == "nt":  # Windows
            normalized = normalized.lower()

        return normalized

    def _paths_equal(self, path1: str, path2: str) -> bool:
        """Check if two paths point to the same file.

        Args:
            path1: First path
            path2: Second path

        Returns:
            bool: True if the paths point to the same file
        """
        if not path1 or not path2:
            return False

        # Normalize both paths
        norm1 = self._normalize_path(path1)
        norm2 = self._normalize_path(path2)

        # Simple string comparison first (faster)
        if norm1 == norm2:
            return True

        try:
            # Try using samefile for more accurate comparison
            # This handles symbolic links, junctions, etc.
            return os.path.samefile(path1, path2)
        except (OSError, ValueError):
            # If samefile fails (e.g., file doesn't exist or different drives),
            # fall back to normalized path comparison
            return norm1 == norm2

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

            # Print active tasks for debugging
            if active_tasks:
                print(f"[DEBUG] Current active tasks: {len(active_tasks)}")
                for task_id, task in active_tasks.items():
                    print(
                        f"[DEBUG] Task {task_id[:8]}... status: {task.status}, file: {os.path.basename(task.pdf_path)}"
                    )
            else:
                print("[DEBUG] No active tasks")

            # Get all PDF files in the folder
            all_files = [
                f for f in os.listdir(source_folder) if f.lower().endswith(".pdf")
            ]
            print(f"[DEBUG] Found {len(all_files)} total PDF files in source folder")

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
                            print(f"[DEBUG] Skipping previously processed file: {file}")
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
                        print(
                            f"[DEBUG] Skipping file that is being processed in tasks: {task_ids_with_path}"
                        )
                        skipped_active += 1
                        continue

                    # Skip files that are already in use by checking if they can be opened
                    try:
                        # Use a quick try-except to test if the file can be opened
                        with open(full_path, "rb") as f:
                            # Just try to open the file to check if it's accessible
                            pass
                        # If we got here, the file can be opened
                        pdf_files.append(full_path)
                    except PermissionError:
                        # Skip this file as it's locked by another process
                        print(f"[DEBUG] Skipping locked file: {file}")
                        skipped_locked += 1
                        continue

            # Print summary of what we found
            print(
                f"[DEBUG] PDF selection summary: {len(pdf_files)} available, {skipped_processed} skipped (processed), {skipped_active} skipped (active tasks), {skipped_locked} skipped (locked)"
            )

            if not pdf_files:
                return None

            # Return the first available file
            selected_file = sorted(pdf_files)[0]
            print(f"[DEBUG] Selected next PDF file: {selected_file}")
            return selected_file

        except Exception as e:
            print(f"[DEBUG] Error getting next PDF: {str(e)}")
            return None

    def open_pdf(self, pdf_path: str) -> bool:
        """Open a PDF file for viewing/processing.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Close any open document
            self.close_current_pdf()

            # Create new document
            self._current_doc = QPdfDocument(self)
            self._current_doc.load(pdf_path)
            self._current_path = pdf_path
            self._rotation = 0

            return True

        except Exception as e:
            print(f"[DEBUG] Error opening PDF: {str(e)}")
            self.close_current_pdf()
            return False

    def close_current_pdf(self, max_attempts: int = 3) -> None:
        """Close the currently open PDF document with retry logic.

        Args:
            max_attempts: Maximum number of attempts to close the document
        """
        if self._current_doc:
            last_error = None
            for attempt in range(max_attempts):
                try:
                    # Close and cleanup document
                    self._current_doc.close()
                    self._current_doc.deleteLater()
                    print("[DEBUG] Successfully closed PDF document")
                    break
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        print(
                            f"[DEBUG] Retry {attempt + 1}: Error closing PDF: {str(e)}"
                        )
                        import time

                        time.sleep(0.5)  # Short delay between retries
                    else:
                        print(f"[DEBUG] All attempts to close PDF failed: {str(e)}")

            # Always clean up references
            self._current_doc = None
            self._current_path = None
            self._rotation = 0

            # If all attempts failed, log it but continue
            if last_error:
                print("[DEBUG] Cleaned up PDF references despite close errors")

    def clear_cache(self) -> None:
        """Clear any cached data."""
        self.close_current_pdf()

    def generate_output_path(self, template: str, data: Dict[str, Any]) -> str:
        """Generate output path based on template and data.

        Args:
            template: Path template string.
            data: Dictionary of data for template substitution.

        Returns:
            str: Generated output path.
        """
        try:
            print(f"[DEBUG] Generating output path with template: '{template}'")
            print(f"[DEBUG] Template data keys: {sorted(data.keys())}")

            # Create a copy of the data to avoid modifying the original
            template_data = data.copy()

            # Clean Excel Row information from all string values
            for key in list(template_data.keys()):
                if isinstance(template_data[key], str):
                    # Remove Excel Row information from the value
                    import re

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
                    print(f"[DEBUG] Found NaT value for {key}, using fallback")
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
                    print(
                        f"[DEBUG] Template data['{key}']: {value_str} (type: {value_type})"
                    )

            # Let the template manager handle the formatting with the improved implementation
            try:
                # The updated template manager now handles both curly brace and ${} formats
                result = self.template_manager.format_path(template, template_data)
                print(f"[DEBUG] Generated path: {result}")

                # If we still have unresolved template variables after processing
                if ("{" in result and "}" in result) or (
                    "${" in result and "}" in result
                ):
                    print(
                        f"[DEBUG] Warning: Output path still has unresolved variables: {result}"
                    )
                    # Try basic substitution for any remaining variables
                    import re

                    result = re.sub(r"\{[^}]+\}", "_", result)
                    result = re.sub(r"\$\{[^}]+\}", "_", result)
                    print(f"[DEBUG] Cleaned path: {result}")
            except Exception as e:
                print(f"[DEBUG] Template manager error: {str(e)}")
                # Fallback path with timestamp
                result = os.path.join(
                    template_data.get("processed_folder", "processed"),
                    f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                )

            # Normalize path separators
            result = result.replace("/", os.path.sep).replace("\\", os.path.sep)

            # Replace any invalid characters in the final path
            invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]
            for char in invalid_chars:
                result = result.replace(char, "_")

            return result
        except Exception as e:
            print(f"[DEBUG] Error generating output path: {str(e)}")
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
            normalized_path = self._normalize_path(file_path)
            self._processed_files.add(normalized_path)
            print(
                f"[DEBUG] Marked file as processed (internal tracking): {normalized_path}"
            )

            # Log the full list for debugging
            print(
                f"[DEBUG] Current processed files count: {len(self._processed_files)}"
            )

            # Immediately update our memory of processed files
            # This ensures future get_next_pdf calls will respect this newly processed file
            import gc

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
        # Normalize the source path to ensure consistent handling
        source_path = task.pdf_path.replace("/", os.path.sep).replace("\\", os.path.sep)
        print(f"[DEBUG] Processing PDF file: {source_path}")

        if not os.path.exists(source_path):
            print(f"[DEBUG] PDF file not found: {source_path}")
            raise FileNotFoundError(f"PDF file not found: {source_path}")

        # Store original location for potential revert operation
        task.original_pdf_location = source_path

        # Force close any open handles to this file
        self._ensure_file_released(source_path)

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

                # Normalize output path for consistent handling
                output_path = output_path.replace("/", os.path.sep).replace(
                    "\\", os.path.sep
                )
                print(f"[DEBUG] Final output path: {output_path}")

                # Ensure output directory exists
                try:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    print(
                        f"[DEBUG] Created output directory: {os.path.dirname(output_path)}"
                    )
                except Exception as e:
                    print(f"[DEBUG] Error creating output directory: {str(e)}")
                    raise ValueError(f"Could not create output directory: {str(e)}")

                # Copy PDF to temporary location
                temp_pdf = os.path.join(temp_dir, "temp.pdf")
                try:
                    shutil.copy2(source_path, temp_pdf)
                    print(f"[DEBUG] Copied PDF to temporary location: {temp_pdf}")
                except Exception as e:
                    print(f"[DEBUG] Error copying PDF to temp location: {str(e)}")
                    raise ValueError(
                        f"Could not copy PDF to temporary location: {str(e)}"
                    )

                # Create a new document for rotation if needed
                if task.rotation_angle != 0:
                    try:
                        # Store rotation in task metadata for viewer
                        task.metadata = {"rotation": task.rotation_angle}
                        print(
                            f"[DEBUG] Stored rotation of {task.rotation_angle} degrees in metadata"
                        )
                    except Exception as e:
                        print(f"[DEBUG] Error storing rotation metadata: {str(e)}")
                        # Continue even if metadata storage fails

                # Move to final location
                try:
                    # Make a regular copy to handle cross-device links
                    shutil.copy2(source_path, output_path)
                    print(
                        f"[DEBUG] Successfully copied PDF to final location: {output_path}"
                    )

                    # Set the processed location in the task
                    task.processed_pdf_location = output_path

                    # Remove the original file from the source folder
                    try:
                        # Try to remove with retries
                        if self._remove_file_with_retry(source_path):
                            print(
                                "[DEBUG] Successfully removed or renamed the original file."
                            )
                        else:
                            # If removal failed, mark the file as processed in our tracking
                            self.mark_file_processed(source_path)
                    except Exception as e:
                        print(
                            f"[DEBUG] Warning: Could not remove original PDF: {str(e)}"
                        )
                        # Mark the file as processed even if removal failed
                        self.mark_file_processed(source_path)

                    print("[DEBUG] PDF processing completed successfully")
                except Exception as e:
                    print(f"[DEBUG] Error moving PDF to final location: {str(e)}")
                    raise ValueError(f"Could not move PDF to final location: {str(e)}")

            except Exception as e:
                print(f"[DEBUG] Error processing PDF: {str(e)}")
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
        import time

        for attempt in range(max_attempts):
            try:
                os.remove(file_path)
                print(f"[DEBUG] Removed original PDF from source folder: {file_path}")
                return True
            except Exception as e:
                if attempt < max_attempts - 1:
                    print(
                        f"[DEBUG] Removal attempt {attempt + 1} failed: {str(e)}, retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    # Last attempt failed, try to rename the file instead
                    try:
                        # Create a new filename with .processed.pdf
                        dir_name = os.path.dirname(file_path)
                        base_name = os.path.basename(file_path)
                        name_without_ext, ext = os.path.splitext(base_name)
                        new_name = f"{name_without_ext}.processed{ext}"
                        new_path = os.path.join(dir_name, new_name)

                        # Try to rename the file
                        os.rename(file_path, new_path)
                        print(
                            f"[DEBUG] Could not remove file, renamed instead to: {new_path}"
                        )
                        return True
                    except Exception as rename_error:
                        # If rename also fails, re-raise the original exception
                        print(f"[DEBUG] Failed to rename file: {str(rename_error)}")
                        raise e

        return False

    def revert_pdf_location(self, task: PDFTask) -> bool:
        """Revert a PDF to its original location.

        Args:
            task: PDFTask object containing processing details.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            if (
                not task
                or not task.processed_pdf_location
                or not task.original_pdf_location
            ):
                print("[DEBUG] Cannot revert: missing required task information")
                return False

            if not os.path.exists(task.processed_pdf_location):
                print(f"[DEBUG] Processed PDF not found: {task.processed_pdf_location}")
                return False

            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(task.original_pdf_location), exist_ok=True)

            # Move the file back to its original location
            shutil.move(task.processed_pdf_location, task.original_pdf_location)
            print(
                f"[DEBUG] Reverted PDF from {task.processed_pdf_location} to {task.original_pdf_location}"
            )

            return True

        except Exception as e:
            print(f"[DEBUG] Error reverting PDF: {str(e)}")
            return False

    def _ensure_file_released(self, file_path: str, max_attempts: int = 3) -> None:
        """Ensure any resources for the file are released with retry logic.

        Args:
            file_path: Path to the file to release
            max_attempts: Maximum number of attempts to release the file
        """
        # Use normalized paths for comparison
        normalized_path = self._normalize_path(file_path)
        current_normalized = (
            self._normalize_path(self._current_path) if self._current_path else None
        )

        # If this is the current open document, close it with retries
        if normalized_path == current_normalized and self._current_doc is not None:
            self.close_current_pdf(max_attempts=max_attempts)

        # Try to verify file is released by attempting to open it
        for attempt in range(max_attempts):
            try:
                with open(file_path, "rb") as test_file:
                    # Just testing if we can open it
                    pass
                print(f"[DEBUG] Verified file is released: {file_path}")
                return
            except PermissionError:
                if attempt < max_attempts - 1:
                    print(
                        f"[DEBUG] Retry {attempt + 1}: File still locked: {file_path}"
                    )
                    import time

                    time.sleep(0.5)  # Short delay between retries
                    continue
                else:
                    print(
                        f"[DEBUG] Warning: Could not verify file release after {max_attempts} attempts: {file_path}"
                    )
            except FileNotFoundError:
                # File doesn't exist, so no lock to worry about
                print(f"[DEBUG] File does not exist, no lock to release: {file_path}")
                return
            except Exception as e:
                print(f"[DEBUG] Unexpected error checking file lock: {str(e)}")
                return

    def cleanup_processed_files(self, folder: str) -> None:
        """Clean up files that were marked as processed but not deleted.

        Args:
            folder: Folder to check for processed files
        """
        if not os.path.exists(folder):
            return

        try:
            for file in os.listdir(folder):
                if file.lower().endswith(".processed.pdf"):
                    file_path = os.path.join(folder, file)
                    try:
                        # Try to delete the processed file
                        os.remove(file_path)
                        print(f"[DEBUG] Cleaned up processed file: {file_path}")
                    except Exception as e:
                        print(
                            f"[DEBUG] Could not clean up processed file: {file_path}, error: {str(e)}"
                        )
        except Exception as e:
            print(f"[DEBUG] Error cleaning up processed files: {str(e)}")
