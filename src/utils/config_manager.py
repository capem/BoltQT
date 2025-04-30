from __future__ import annotations
from typing import Dict, Any, List, Callable, Optional
import json
import os
import traceback
from PyQt6.QtCore import QObject, pyqtSignal
from .logger import get_logger


class ConfigManager(QObject):
    """Manages application configuration settings."""

    # Signal emitted when configuration changes
    config_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        # Default configuration template
        self._config_template: Dict[str, Any] = {
            "document_type": "",
            "source_folder": "",
            "excel_file": "",
            "excel_sheet": "",
            "processed_folder": "",
            "skip_folder": "",  # New: folder for skipped files
            "output_template": "",
            "filter1_column": "",
            "filter2_column": "",
            "filter3_column": "",
            "filter4_column": "",
            "prompt": "",
            "field_mappings": {},
            "vision": {
                "enabled": False,
                "gemini_api_key": "",
                "model": "gemini-2.0-flash",
                "supplier_match_threshold": 0.75,
                "default_language": "fr",
                "ocr_preprocessing": True,
            },
        }

        # Main config file - only config.json
        self._config_file = "config.json"

        # Current/active configuration
        self._current_config = self._config_template.copy()

        # Current active preset name (None if using default unsaved configuration)
        self._current_preset: Optional[str] = None

        # Change callbacks
        self._change_callbacks: List[Callable] = []

        # Load configuration
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from config.json."""
        logger = get_logger()
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    configs = json.load(f)

                    # Check for _last_used_preset field
                    last_preset = configs.get("_last_used_preset")

                    if last_preset and last_preset in configs:
                        # Load the last used preset
                        self._current_config = self._merge_with_template(
                            configs[last_preset]
                        )
                        self._current_preset = last_preset
                        logger.info(f"Loaded configuration from last used preset: {last_preset}")
                    else:
                        # Try to load the first available preset
                        preset_names = [
                            name
                            for name in configs.keys()
                            if name != "_last_used_preset"
                        ]
                        if preset_names:
                            first_preset = preset_names[0]
                            self._current_config = self._merge_with_template(
                                configs[first_preset]
                            )
                            self._current_preset = first_preset
                            configs["_last_used_preset"] = first_preset
                            self._save_configs(configs)
                            logger.info(f"Loaded configuration from first preset: {first_preset}")
                        else:
                            # Create a default config if no presets exist
                            logger.warning("No presets found, using default configuration")
            else:
                # Create default configs file with initial preset
                configs = {
                    "Preset: Default": self._current_config,
                    "_last_used_preset": "Preset: Default",
                }
                self._current_preset = "Preset: Default"
                self._save_configs(configs)
                logger.info("Created new config.json with default preset")

        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

    def _merge_with_template(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge loaded config with template to ensure all keys exist."""
        result = self._config_template.copy()

        # Top level merge
        for key, value in config.items():
            if key in result:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    # Deep merge for nested objects like 'vision'
                    for subkey, subvalue in value.items():
                        result[key][subkey] = subvalue
                else:
                    result[key] = value
            else:
                # Add non-template keys
                result[key] = value

        return result

    def _save_configs(self, configs: Dict[str, Any]) -> None:
        """Save configs to file."""
        logger = get_logger()
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(configs, f, indent=2)
            logger.debug(f"Saved configuration to {self._config_file}")
        except Exception as e:
            logger.error(f"Error saving configs: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self._current_config.copy()

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        changed = False

        # Update current config
        for key, value in new_config.items():
            if key in self._current_config:
                if isinstance(value, dict) and isinstance(
                    self._current_config[key], dict
                ):
                    # Deep compare for dictionaries
                    if json.dumps(
                        self._current_config[key], sort_keys=True
                    ) != json.dumps(value, sort_keys=True):
                        self._current_config[key] = value
                        changed = True
                elif self._current_config[key] != value:
                    self._current_config[key] = value
                    changed = True

        if changed:
            # Load existing configs
            try:
                if os.path.exists(self._config_file):
                    with open(self._config_file, "r", encoding="utf-8") as f:
                        configs = json.load(f)
                else:
                    configs = {}

                # Update the current named preset if one is active
                if self._current_preset and self._current_preset in configs:
                    configs[self._current_preset] = self._current_config

                    # Make sure _last_used_preset is set
                    configs["_last_used_preset"] = self._current_preset
                else:
                    # We're modifying an unsaved configuration,
                    # but don't overwrite any presets in the file
                    pass

                # Save configs
                self._save_configs(configs)

                # Emit signal
                self.config_changed.emit()

                # Call callbacks
                for callback in self._change_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger = get_logger()
                        logger.error(f"Error in config change callback: {str(e)}")
                        if hasattr(e, "__traceback__"):
                            logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

            except Exception as e:
                logger = get_logger()
                logger.error(f"Error updating configs: {str(e)}")
                if hasattr(e, "__traceback__"):
                    logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

    def load_preset(self, preset_name: str) -> None:
        """Load a preset as the current configuration."""
        if not preset_name:
            return

        try:
            # Load configs
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    configs = json.load(f)

                if preset_name in configs and preset_name != "_last_used_preset":
                    # Set as current configuration
                    self._current_config = self._merge_with_template(
                        configs[preset_name]
                    )
                    self._current_preset = preset_name

                    # Update the _last_used_preset
                    configs["_last_used_preset"] = preset_name
                    self._save_configs(configs)

                    # Emit signal
                    self.config_changed.emit()

                    # Call callbacks
                    for callback in self._change_callbacks:
                        try:
                            callback()
                        except Exception as e:
                            logger = get_logger()
                            logger.error(f"Error in config change callback: {str(e)}")
                            if hasattr(e, "__traceback__"):
                                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

                    logger = get_logger()
                    logger.info(f"Loaded preset: {preset_name}")
                else:
                    logger = get_logger()
                    logger.warning(f"Preset not found: {preset_name}")
        except Exception as e:
            logger = get_logger()
            logger.error(f"Error loading preset: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

    def save_preset(self, preset_name: str) -> None:
        """Save current configuration as a named preset."""
        if not preset_name or preset_name == "_last_used_preset":
            return

        try:
            # Load existing configs
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    configs = json.load(f)
            else:
                configs = {}

            # Add current config as new preset
            configs[preset_name] = self._current_config
            self._current_preset = preset_name

            # Update the _last_used_preset
            configs["_last_used_preset"] = preset_name

            # Save configs
            self._save_configs(configs)

            logger = get_logger()
            logger.info(f"Saved preset: {preset_name}")
        except Exception as e:
            logger = get_logger()
            logger.error(f"Error saving preset: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

    def delete_preset(self, preset_name: str) -> None:
        """Delete a preset."""
        if not preset_name or preset_name == "_last_used_preset":
            return

        try:
            # Load configs
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    configs = json.load(f)

                if preset_name in configs:
                    # Delete preset
                    del configs[preset_name]

                    # Reset current preset if it was the deleted one
                    if self._current_preset == preset_name:
                        self._current_preset = None

                        # If this was the last used preset, find another preset to use
                        if configs.get("_last_used_preset") == preset_name:
                            preset_names = [
                                name
                                for name in configs.keys()
                                if name != "_last_used_preset"
                            ]
                            if preset_names:
                                configs["_last_used_preset"] = preset_names[0]
                            else:
                                # No presets left
                                if "_last_used_preset" in configs:
                                    del configs["_last_used_preset"]

                    # Save configs
                    self._save_configs(configs)

                    logger = get_logger()
                    logger.info(f"Deleted preset: {preset_name}")
                else:
                    logger = get_logger()
                    logger.warning(f"Preset not found: {preset_name}")
        except Exception as e:
            logger = get_logger()
            logger.error(f"Error deleting preset: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

    def get_preset_names(self) -> List[str]:
        """Get list of available preset names."""
        preset_names = []

        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    configs = json.load(f)

                preset_names = [
                    name for name in configs.keys() if name != "_last_used_preset"
                ]
        except Exception as e:
            logger = get_logger()
            logger.error(f"Error getting preset names: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

        return preset_names

    def get_current_preset_name(self) -> str:
        """Get name of the currently active preset or empty string if using default configuration."""
        return self._current_preset or ""

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
