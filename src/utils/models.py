from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class PDFTask:
    """Represents a PDF processing task."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pdf_path: str = ""
    filter_values: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, processing, completed, failed, reverted, skipped
    error_msg: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    row_idx: int = -1
    original_excel_hyperlink: Optional[str] = None
    original_pdf_location: Optional[str] = None
    processed_pdf_location: Optional[str] = (
        None  # Path where the PDF was moved after processing
    )
    versioned_pdf_path: Optional[str] = None  # Path of the 'old_' versioned file if one was created
    rotation_angle: int = 0
    skip_type: str = "in_place"  # 'in_place' (default) or 'to_folder'
    created_new_row: bool = False  # True if this task created a new Excel row

    @staticmethod
    def generate_id() -> str:
        """Generate a unique task ID."""
        return str(uuid.uuid4())

    def duration(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def can_revert(self) -> bool:
        """Check if the task can be reverted."""
        # For tasks that created new rows, we can revert if we have the basic info
        if self.created_new_row:
            return (
                self.status == "completed"
                and self.row_idx >= 0
                and self.original_pdf_location is not None
                and self.processed_pdf_location is not None
            )

        # For tasks that updated existing rows, we need the original hyperlink
        return (
            self.status == "completed"
            and self.original_excel_hyperlink is not None
            and self.original_pdf_location is not None
            and self.processed_pdf_location is not None
        )
