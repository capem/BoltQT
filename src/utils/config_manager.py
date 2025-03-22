from __future__ import annotations
from typing import Dict, Any, List, Callable
import json
import os
from PyQt6.QtCore import QObject, pyqtSignal


class ConfigManager(QObject):
    """Manages application configuration settings."""

    # Signal emitted when configuration changes
    config_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._config: Dict[str, Any] = {
            "source_folder": "",
            "excel_file": "",
            "excel_sheet": "",
            "processed_folder": "",
            "output_template": "",
            "filter1_column": "",
            "filter2_column": "",
            "filter3_column": "",
            "filter4_column": "",
            "vision": {
                "enabled": False,
                "gemini_api_key": "",
                "model": "gemini-2.0-flash",
                "supplier_match_threshold": 0.75,
                "auto_populate_fields": True,
                "default_language": "fr",
                "ocr_preprocessing": True
            }
        }
        self._config_file = "config.json"
        self._change_callbacks: List[Callable] = []

        # Load existing config if available
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file."""
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # Only update existing keys
                    for key in self._config:
                        if key in loaded_config:
                            self._config[key] = loaded_config[key]
        except Exception as e:
            print(f"[DEBUG] Error loading config: {str(e)}")

    def save_config(self) -> None:
        """Save configuration to file."""
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"[DEBUG] Error saving config: {str(e)}")

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self._config.copy()

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        changed = False
        for key, value in new_config.items():
            if key in self._config and self._config[key] != value:
                self._config[key] = value
                changed = True

        if changed:
            self.save_config()
            # Emit signal
            self.config_changed.emit()
            # Call callbacks
            for callback in self._change_callbacks:
                try:
                    callback()
                except Exception as e:
                    print(f"[DEBUG] Error in config change callback: {str(e)}")

    def add_change_callback(self, callback: Callable) -> None:
        """Add a callback to be called when configuration changes."""
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable) -> None:
        """Remove a configuration change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    def clear_callbacks(self) -> None:
        """Clear all configuration change callbacks."""
        self._change_callbacks.clear()
