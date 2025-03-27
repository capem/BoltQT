"""
Path handling utilities to ensure consistent path normalization and formatting.
This module centralizes path handling to avoid issues with drive letters,
UNC paths, and relative paths across the application.
"""

from __future__ import annotations
import os
import re
from typing import Tuple


def normalize_path(path: str) -> str:
    """Normalize paths with consistent handling of drive letters and separators.
    
    Args:
        path: The path to normalize
        
    Returns:
        str: Normalized path with consistent separators and preserved drive letters
    """
    if not path:
        return ""
    
    # Handle UNC paths specially
    if path.startswith('\\\\') or path.startswith('//'):
        # Convert to a standard format (Windows UNC style)
        path = path.replace('/', '\\')
        if not path.startswith('\\\\'):
            path = '\\\\' + path[2:]
        # Avoid normalizing the server and share part of UNC paths
        parts = path[2:].split('\\', 2)
        if len(parts) >= 2:
            server, share = parts[0], parts[1]
            rest = parts[2] if len(parts) > 2 else ""
            # Normalize only the path after server and share
            normalized_rest = os.path.normpath(rest) if rest else ""
            return f'\\\\{server}\\{share}\\{normalized_rest}'
        return path
    
    # Handle regular paths with drive letters
    drive, rest = os.path.splitdrive(path)
    # Preserve drive letters (e.g., C:, D:) without mangling
    if drive:
        # Normalize the path portion (after drive letter) with proper separators
        normalized_rest = os.path.normpath(rest.replace('/', os.sep).replace('\\', os.sep))
        return f"{drive}{normalized_rest}"
    
    # Handle regular paths without drive letters
    return os.path.normpath(path.replace('/', os.sep).replace('\\', os.sep))


def make_relative_path(base_path: str, target_path: str) -> str:
    """Create a proper relative path between two locations.
    
    Args:
        base_path: The base path (typically where the Excel file is)
        target_path: The target path (typically where the PDF is)
        
    Returns:
        str: Relative path or absolute path if on different drives
    """
    # Normalize both paths first
    base_norm = normalize_path(base_path)
    target_norm = normalize_path(target_path)
    
    # Extract drive/UNC components
    base_drive, base_rest = split_drive_or_unc(base_norm)
    target_drive, target_rest = split_drive_or_unc(target_norm)
    
    # If on different drives/servers, we can't create a relative path
    if base_drive.lower() != target_drive.lower():
        print(f"[DEBUG] Cannot create relative path across different drives: {base_drive} vs {target_drive}")
        return target_norm  # Return absolute path
    
    try:
        # Create relative path
        rel_path = os.path.relpath(target_norm, os.path.dirname(base_norm))
        print(f"[DEBUG] Created relative path: {rel_path}")
        return rel_path
    except ValueError as e:
        print(f"[DEBUG] Error creating relative path: {str(e)}")
        return target_norm  # Fallback to absolute path


def split_drive_or_unc(path: str) -> Tuple[str, str]:
    """Split path into drive/UNC server+share and the rest.
    
    This handles both drive letters (C:) and UNC paths (\\server\share).
    
    Args:
        path: Path to split
        
    Returns:
        tuple: (drive_or_unc, rest_of_path)
    """
    if path.startswith('\\\\'):
        # Handle UNC path
        parts = path[2:].split('\\', 2)
        if len(parts) >= 2:
            server, share = parts[0], parts[1]
            rest = '\\' + parts[2] if len(parts) > 2 else ""
            return f'\\\\{server}\\{share}', rest
        return path, ""
    
    # Regular os.path.splitdrive for local paths
    return os.path.splitdrive(path)


def is_same_path(path1: str, path2: str) -> bool:
    """Check if two paths point to the same file, normalizing them first.
    
    Args:
        path1: First path
        path2: Second path
        
    Returns:
        bool: True if the paths point to the same file
    """
    if not path1 or not path2:
        return False
        
    # Normalize both paths
    norm1 = normalize_path(path1)
    norm2 = normalize_path(path2)
    
    # Simple string comparison (case-insensitive on Windows)
    if os.name == 'nt':  # Windows
        return norm1.lower() == norm2.lower()
    else:
        return norm1 == norm2


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename (not path) by replacing invalid characters.
    
    Args:
        filename: Name of file without path
        
    Returns:
        str: Sanitized filename
    """
    # Don't process if empty
    if not filename:
        return ""
    
    # Characters not allowed in filenames on Windows and most systems
    invalid_chars = r'[<>:"/\\|?*\0\r\n\t]'
    
    # Replace invalid characters with underscore
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove leading/trailing whitespace and dots (problematic on some systems)
    sanitized = sanitized.strip(". ")
    
    # Collapse multiple spaces into one
    sanitized = " ".join(sanitized.split())
    
    # Ensure we have a valid filename even if everything was sanitized away
    if not sanitized:
        return "_"
    
    return sanitized


def sanitize_path_component(component: str) -> str:
    """Sanitize a path component while preserving drive letters and UNC paths.
    
    Args:
        component: Path component to sanitize
        
    Returns:
        str: Sanitized path component
    """
    if not component:
        return ""
        
    # Handle drive letters specially
    drive, rest = os.path.splitdrive(component)
    if drive:
        # Only sanitize the non-drive part
        return drive + sanitize_filename(rest)
    
    # Handle UNC paths specially
    if component.startswith('\\\\') or component.startswith('//'):
        # Preserve server and share portions
        parts = re.split(r'[/\\]', component.lstrip('/\\'), 2)
        if len(parts) >= 2:
            server, share = parts[0], parts[1]
            rest = parts[2] if len(parts) > 2 else ""
            return f'\\\\{server}\\{share}\\{sanitize_filename(rest)}'
    
    # Regular path component
    return sanitize_filename(component)