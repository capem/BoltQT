from __future__ import annotations

import copy
import json
import os
import traceback
from typing import Any, Callable, Dict, List, Optional

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
            "skip_folder": "",
            "output_template": "",
            "num_filters": 4,
            "filter_columns": ["", "", "", ""],
            "prompt": "",
            "field_mappings": {},
            "hyperlink_mode": {
                "standard": True,
                "enhanced": False
            },
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

    def _migrate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate old config format to the new one."""
        if "filter1_column" in config:
            filter_columns = []
            i = 1
            while f"filter{i}_column" in config:
                filter_columns.append(config.pop(f"filter{i}_column"))
                i += 1
            config["num_filters"] = len(filter_columns)
            config["filter_columns"] = filter_columns
        return config

    def _merge_with_template(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge loaded config with template and migrate if necessary."""
        config = self._migrate_config(config)
        result = self._config_template.copy()

        # Top level merge
        for key, value in config.items():
            if key in result:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    # Deep merge for nested objects like 'vision'
                    result[key].update(value)
                else:
                    result[key] = value
            else:
                # Add non-template keys
                result[key] = value

        # Ensure filter_columns matches num_filters
        num_filters = result.get("num_filters", 0)
        filter_columns = result.get("filter_columns", [])
        if len(filter_columns) < num_filters:
            filter_columns.extend([""] * (num_filters - len(filter_columns)))
        elif len(filter_columns) > num_filters:
            result["filter_columns"] = filter_columns[:num_filters]

        return result

    def _save_configs(self, configs: Dict[str, Any]) -> None:
        """Save configs to file."""
        logger = get_logger()
        try:
            # Log what we're about to save
            preset_names = [name for name in configs.keys() if name != "_last_used_preset"]
            logger.debug(f"Saving configuration with {len(preset_names)} presets: {preset_names}")
            logger.debug(f"Current active preset: {configs.get('_last_used_preset', 'None')}")

            # Make sure we're saving a copy, not a reference
            configs_to_save = copy.deepcopy(configs)

            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(configs_to_save, f, indent=2)
            logger.debug(f"Saved configuration to {self._config_file}")

            # Verify the file was written correctly
            if os.path.exists(self._config_file):
                file_size = os.path.getsize(self._config_file)
                logger.debug(f"Config file size after save: {file_size} bytes")
                if file_size == 0:
                    logger.error("Config file is empty after save!")
        except Exception as e:
            logger.error(f"Error saving configs: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self._current_config.copy()

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        logger = get_logger()
        logger.debug(f"Updating config with new values. Current preset: {self._current_preset}")

        changed = False
        changed_keys = []

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
                        logger.debug(f"Updating nested dict key: {key}")
                        self._current_config[key] = value.copy()  # Use copy to avoid reference issues
                        changed = True
                        changed_keys.append(key)
                elif self._current_config[key] != value:
                    logger.debug(f"Updating key: {key}, old value: {self._current_config[key]}, new value: {value}")
                    self._current_config[key] = value
                    changed = True
                    changed_keys.append(key)
            else:
                # Add keys that aren't in the template but are in the update
                logger.debug(f"Adding new key not in template: {key}")
                self._current_config[key] = value
                changed = True
                changed_keys.append(key)

        if changed:
            logger.info(f"Config changed. Modified keys: {changed_keys}")
            # Load existing configs
            try:
                if os.path.exists(self._config_file):
                    with open(self._config_file, "r", encoding="utf-8") as f:
                        configs = json.load(f)
                    logger.debug(f"Loaded existing configs from {self._config_file}")
                else:
                    configs = {}
                    logger.debug(f"Config file {self._config_file} does not exist, creating new configs")

                # Update the current named preset if one is active
                if self._current_preset and self._current_preset in configs:
                    logger.debug(f"Updating preset '{self._current_preset}' with new config values")
                    # Make a deep copy to avoid reference issues
                    configs[self._current_preset] = copy.deepcopy(self._current_config)

                    # Make sure _last_used_preset is set
                    configs["_last_used_preset"] = self._current_preset

                    # Log the keys being saved
                    logger.debug(f"Keys in preset being saved: {list(configs[self._current_preset].keys())}")
                else:
                    # We're modifying an unsaved configuration,
                    # but don't overwrite any presets in the file
                    logger.warning(f"No active preset or preset '{self._current_preset}' not found in configs. Current preset: '{self._current_preset}'")

                    # If we have a current preset name but it's not in configs, add it
                    if self._current_preset:
                        logger.info(f"Adding missing preset '{self._current_preset}' to configs")
                        configs[self._current_preset] = copy.deepcopy(self._current_config)
                        configs["_last_used_preset"] = self._current_preset

                # Save configs
                self._save_configs(configs)

                # Emit signal
                logger.debug("Emitting config_changed signal")
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
        else:
            logger.info("No changes detected in configuration update")

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
        logger = get_logger()

        if not preset_name or preset_name == "_last_used_preset":
            logger.warning(f"Invalid preset name: {preset_name}")
            return

        try:
            logger.debug(f"Saving current configuration as preset: {preset_name}")

            # Load existing configs
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    configs = json.load(f)
                logger.debug(f"Loaded existing configs from {self._config_file}")
            else:
                configs = {}
                logger.debug("No existing config file, creating new configs")

            # Make a deep copy of the current config to avoid reference issues
            config_to_save = copy.deepcopy(self._current_config)

            # Add current config as new preset
            configs[preset_name] = config_to_save
            self._current_preset = preset_name

            # Update the _last_used_preset
            configs["_last_used_preset"] = preset_name

            # Log what we're about to save
            logger.debug(f"Current config keys: {list(config_to_save.keys())}")

            # Save configs
            self._save_configs(configs)

            # Verify the preset was saved correctly
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    saved_configs = json.load(f)
                if preset_name in saved_configs:
                    logger.debug(f"Verified preset {preset_name} was saved correctly")
                else:
                    logger.error(f"Preset {preset_name} not found in saved config file!")

            logger.info(f"Saved preset: {preset_name}")
        except Exception as e:
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
