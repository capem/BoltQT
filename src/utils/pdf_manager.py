from __future__ import annotations
from typing import Dict, Any, Optional, List
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import fitz  # PyMuPDF
import shutil
from PyQt6.QtCore import QObject
from .models import PDFTask
from .template_manager import TemplateManager

class PDFManager(QObject):
    """Manages PDF file operations."""
    
    def __init__(self) -> None:
        """Initialize PDFManager."""
        super().__init__()
        self._current_doc: Optional[fitz.Document] = None
        self._current_path: Optional[str] = None
        self._rotation: int = 0
        self.template_manager = TemplateManager()
    
    def get_next_pdf(self, source_folder: str, active_tasks: Dict[str, PDFTask]) -> Optional[str]:
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
                
            # Get all PDF files in the folder
            pdf_files = []
            for file in os.listdir(source_folder):
                if file.lower().endswith('.pdf'):
                    full_path = os.path.join(source_folder, file)
                    if full_path not in active_tasks:
                        pdf_files.append(full_path)
            
            if not pdf_files:
                return None
            
            # Return the first available file
            return sorted(pdf_files)[0]
            
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
            
            # Open new document
            self._current_doc = fitz.open(pdf_path)
            self._current_path = pdf_path
            self._rotation = 0
            
            return True
            
        except Exception as e:
            print(f"[DEBUG] Error opening PDF: {str(e)}")
            self.close_current_pdf()
            return False
    
    def close_current_pdf(self) -> None:
        """Close the currently open PDF document."""
        if self._current_doc:
            try:
                self._current_doc.close()
            except Exception as e:
                print(f"[DEBUG] Error closing PDF: {str(e)}")
            finally:
                self._current_doc = None
                self._current_path = None
                self._rotation = 0
    
    def get_current_page(self) -> Optional[fitz.Page]:
        """Get the current page of the open PDF."""
        if not self._current_doc:
            return None
            
        try:
            return self._current_doc[0]  # Always return first page
        except Exception as e:
            print(f"[DEBUG] Error getting PDF page: {str(e)}")
            return None
    
    def rotate_page(self, clockwise: bool = True) -> None:
        """Rotate the current page.
        
        Args:
            clockwise: True for clockwise rotation, False for counter-clockwise.
        """
        rotation = 90 if clockwise else -90
        self._rotation = (self._rotation + rotation) % 360
    
    def get_rotation(self) -> int:
        """Get the current rotation angle."""
        return self._rotation
    
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
        return self.template_manager.format_path(template, data)
    
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
        if not os.path.exists(task.pdf_path):
            raise FileNotFoundError(f"PDF file not found: {task.pdf_path}")
            
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
                
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Copy PDF to temporary location
                temp_pdf = os.path.join(temp_dir, "temp.pdf")
                shutil.copy2(task.pdf_path, temp_pdf)
                
                # Apply rotation if needed
                if task.rotation_angle != 0:
                    doc = fitz.open(temp_pdf)
                    page = doc[0]
                    page.set_rotation(task.rotation_angle)
                    doc.save(temp_pdf)
                    doc.close()
                
                # Move to final location
                shutil.move(temp_pdf, output_path)
                
            except Exception as e:
                print(f"[DEBUG] Error processing PDF: {str(e)}")
                raise