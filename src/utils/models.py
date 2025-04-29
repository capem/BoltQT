from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid


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
    rotation_angle: int = 0
    skip_type: str = "in_place"  # 'in_place' (default) or 'to_folder'

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
        return (
            self.status == "completed"
            and self.original_excel_hyperlink is not None
            and self.original_pdf_location is not None
            and self.processed_pdf_location is not None
        )
