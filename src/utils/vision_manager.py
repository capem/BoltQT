from __future__ import annotations

import json
import os
import re
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from .excel_manager import ExcelManager
from .logger import get_logger


class VisionParsingError(Exception):
    """Exception raised for errors in the vision preprocessing process."""

    pass


class VisionManager:
    """Manager for vision-related preprocessing operations.

    This class handles all vision preprocessing functionality used for filter auto-population,
    keeping it separate from the PDF processing workflow.
    """

    def __init__(self, config_manager, excel_manager=None):
        """Initialize the Vision Manager.

        Args:
            config_manager: The application configuration manager
            excel_manager: Optional ExcelManager instance to reuse (avoid duplicate loading)
        """
        self.config_manager = config_manager
        self.excel_manager = excel_manager  # Reuse existing ExcelManager if provided
        self._vision_parser = None
        self._initialize_vision_service()

    def _initialize_vision_service(self):
        """Initialize the vision parser service."""
        if self.config_manager:
            # Check if API key exists before initializing
            config = self.config_manager.get_config()
            vision_config = config.get("vision", {})
            api_key = vision_config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")

            logger = get_logger()
            if api_key:
                self._vision_parser = VisionParserService(self.config_manager, self.excel_manager)
                logger.debug("Vision preprocessing service initialized")
            else:
                self._vision_parser = None
                logger.debug(
                    "Vision preprocessing service not initialized - no API key available"
                )
        else:
            logger = get_logger()
            logger.debug(
                "Cannot initialize vision service - no config manager provided"
            )

    def preprocess_pdf(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Run vision preprocessing on a PDF to extract data for filter population.

        Args:
            pdf_path: Path to the PDF file to process

        Returns:
            Optional dict containing extracted data for filter population,
            or None if preprocessing fails or is disabled
        """
        if not self.is_vision_enabled():
            # Log message already printed in is_vision_enabled()
            return None

        logger = get_logger()
        if not self._vision_parser:
            logger.debug("Vision preprocessing service is not available")
            return None

        try:
            # Get the current preset configuration from the config manager
            preset_name = self.config_manager.get_current_preset_name()
            document_type = self.config_manager.get_config().get("document_type", "")

            logger.debug(
                f"Running vision preprocessing on {pdf_path} using preset '{preset_name}'"
            )
            if document_type:
                logger.debug(f"Document type: {document_type}")

            # Process the PDF with the current preset configuration
            vision_result = self._vision_parser.process_document(pdf_path)
            logger.debug("Vision preprocessing completed successfully")
            return vision_result
        except VisionParsingError as e:
            logger.error(f"Vision preprocessing error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected vision preprocessing error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def is_vision_enabled(self) -> bool:
        """Check if vision preprocessing is enabled in the configuration.

        Returns:
            bool: True if vision preprocessing is enabled AND a valid API key exists, False otherwise
        """
        if not self.config_manager:
            return False

        # Check configuration
        config = self.config_manager.get_config()
        vision_config = config.get("vision", {})

        logger = get_logger()
        # First check if enabled in config
        if not vision_config.get("enabled", False):
            logger.debug("Vision preprocessing is disabled in configuration")
            return False

        # Then check if API key exists in environment or config
        api_key = vision_config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")

        # Only return true if both enabled and API key exists
        if not api_key:
            logger.debug("Vision preprocessing is disabled - no API key available")
            return False

        return True

    def has_vision_service(self) -> bool:
        """Check if the vision service is available.

        Returns:
            bool: True if vision service is available, False otherwise
        """
        return self._vision_parser is not None


class VisionParserService:
    """Service for extracting information from documents using Google Gemini API for filter preprocessing."""

    def __init__(self, config_manager, excel_manager=None):
        """Initialize the vision preprocessing service with configuration.

        Args:
            config_manager: The application configuration manager
            excel_manager: Optional ExcelManager instance to reuse
        """
        self.config_manager = config_manager
        self.excel_manager = excel_manager  # Reuse existing ExcelManager if provided
        self._init_gemini_client()
        self._fuzzy_matcher = FuzzyMatcher(config_manager, excel_manager)

        # Load suppliers for fuzzy matching
        config = config_manager.get_config()
        field_mappings = config.get("field_mappings", {})
        filter_columns = config.get("filter_columns", [])

        supplier_column_name = "FOURNISSEUR"  # Default

        # Find which filter is mapped to 'supplier_name'
        supplier_filter_key = None
        for field, filter_key in field_mappings.items():
            if field == "supplier_name":
                supplier_filter_key = filter_key
                break

        if supplier_filter_key:
            try:
                # e.g., "filter1" -> 0
                filter_index = int(supplier_filter_key.replace("filter", "")) - 1
                if 0 <= filter_index < len(filter_columns):
                    supplier_column_name = filter_columns[filter_index]
            except (ValueError, IndexError):
                get_logger().warning(
                    f"Could not determine supplier column from mapping: {supplier_filter_key}"
                )

        self._fuzzy_matcher.load_entries_from_excel("supplier", supplier_column_name)

    def _init_gemini_client(self) -> None:
        """Initialize the Gemini API client."""
        config = self.config_manager.get_config()
        vision_config = config.get("vision", {})
        api_key = vision_config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")

        logger = get_logger()
        # Check if API key is available
        if not api_key:
            logger.debug("Gemini API key not found in environment variables or config")

        if api_key:
            self.client = genai.Client(api_key=api_key)
            logger.debug("Gemini API client initialized successfully")
        else:
            logger.warning(
                "No Gemini API key found, vision preprocessing will be disabled"
            )
            self.client = None

    def process_document(self, pdf_path: str) -> Dict[str, Any]:
        """Preprocess a PDF document using vision AI to extract data for filter population.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dict containing extracted document data for filter population

        Raises:
            VisionParsingError: If preprocessing fails
        """
        logger = get_logger()
        # Early check to ensure client is initialized
        if not self.client:
            logger.warning(
                "Vision preprocessing skipped - Gemini client not initialized"
            )
            raise VisionParsingError("Vision preprocessing unavailable - No API key")

        try:
            logger.debug(f"Starting vision preprocessing for document: {pdf_path}")

            # Get configuration for vision preprocessing
            config = self.config_manager.get_config()
            document_type = config.get("document_type", "")

            if document_type:
                logger.debug(f"Document type: {document_type}")

            # Step 1: Convert PDF to images
            logger.debug("Converting PDF to images...")
            image_paths = self._convert_pdf_to_images(pdf_path)
            if not image_paths:
                logger.error("Failed to convert PDF to images")
                raise VisionParsingError("Failed to convert PDF to images")
            logger.debug(f"Generated {len(image_paths)} images from PDF")

            # Step 2: Extract text using Gemini Vision API with prompt from config
            logger.debug("Extracting data from images with Gemini...")

            # Get prompt from config
            prompt = config.get("prompt", "").strip()

            if not prompt:
                logger.error(
                    "No prompt defined in configuration, cannot process document"
                )
                raise VisionParsingError("No prompt defined in configuration")

            # Get field mappings from config
            field_mappings = config.get("field_mappings", {})

            if not field_mappings:
                logger.warning(
                    "No field mappings defined in configuration, document extraction may be incomplete"
                )

            extracted_data = self._extract_document_data(image_paths, prompt)
            logger.debug(
                f"Extracted data for filter population: {json.dumps(extracted_data, indent=2)}"
            )

            # Step 3: Validate supplier with fuzzy matching
            supplier_name = extracted_data.get("supplier_name", "")
            logger.debug(f"Validating extracted supplier name: '{supplier_name}'")
            supplier_validation = self._fuzzy_matcher.find_match(
                supplier_name, "supplier"
            )
            logger.debug(
                f"Supplier validation result: {json.dumps(supplier_validation, indent=2)}"
            )

            # Map extracted data to expected filter fields
            normalized_data = self._map_extracted_fields(
                extracted_data, field_mappings, supplier_validation
            )
            logger.debug(
                f"Normalized data for filters: {json.dumps(normalized_data, indent=2)}"
            )

            # Combine results
            result = {
                "extracted_data": extracted_data,
                "normalized_data": normalized_data,
                "supplier_validation": supplier_validation,
                "validation_status": "validated"
                if supplier_validation["match_found"]
                else "needs_review",
                "confidence_score": supplier_validation.get("confidence", 0),
                "processing_time": datetime.now().isoformat(),
                "document_type": document_type,
            }

            logger.debug(
                f"Vision preprocessing complete. Final result keys: {list(result.keys())}"
            )
            return result

        except Exception as e:
            error_msg = f"Vision preprocessing failed: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error traceback: {traceback.format_exc()}")
            raise VisionParsingError(error_msg)

    def _map_extracted_fields(
        self,
        extracted_data: Dict[str, Any],
        field_mappings: Dict[str, str],
        supplier_validation: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Maps extracted fields to filter fields based on field mappings.

        Args:
            extracted_data: Raw extracted data from vision API
            field_mappings: Mapping of extracted field names to filter names
            supplier_validation: Result of supplier fuzzy matching (optional)

        Returns:
            Dict with normalized field names matching filters
        """
        normalized_data = {}
        logger = get_logger()

        config = self.config_manager.get_config()
        vision_config = config.get("vision", {})
        supplier_match_threshold = vision_config.get("supplier_match_threshold", 0.75)

        for extracted_field, filter_field in field_mappings.items():
            if extracted_field in extracted_data:
                value = extracted_data[extracted_field]

                # Special handling for supplier name
                if extracted_field == "supplier_name" and supplier_validation:
                    if (
                        supplier_validation.get("match_found", False)
                        and supplier_validation.get("confidence", 0)
                        >= supplier_match_threshold
                    ):
                        value = supplier_validation["best_match"]
                        logger.debug(
                            f"Using fuzzy matched supplier name for {filter_field}: '{value}'"
                        )
                    else:
                        logger.debug(
                            f"Using original supplier name for {filter_field}: '{value}'"
                        )

                normalized_data[filter_field] = value

        return normalized_data

    def _convert_pdf_to_images(self, pdf_path: str) -> List[str]:
        """Convert PDF pages to images for processing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of paths to generated images
        """
        logger = get_logger()
        try:
            # This is a placeholder - in a real implementation, you would use a library like pdf2image
            # For now, we'll assume the conversion works and return a dummy path
            logger.debug(f"Converting PDF to images: {pdf_path}")

            # In a real implementation:
            # from pdf2image import convert_from_path
            # images = convert_from_path(pdf_path)
            # image_paths = []
            # for i, image in enumerate(images):
            #     img_path = f"{pdf_path}_page_{i}.jpg"
            #     image.save(img_path, "JPEG")
            #     image_paths.append(img_path)

            # For now, just return the PDF path as a placeholder
            logger.debug(
                "Using PDF path directly as image path (placeholder implementation)"
            )
            return [pdf_path]
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
            logger.error(f"Error traceback: {traceback.format_exc()}")
            return []

    def _extract_document_data(
        self, image_paths: List[str], prompt: str
    ) -> Dict[str, Any]:
        """Extract document data from images using Gemini Vision API with a specific prompt.

        Args:
            image_paths: List of image paths to process
            prompt: Custom prompt for extraction based on document type

        Returns:
            Structured data extracted from the document
        """
        logger = get_logger()
        try:
            if not self.client:
                logger.error(
                    "Cannot extract document data - Gemini client not initialized"
                )
                raise VisionParsingError("Gemini client not initialized")

            logger.debug(f"Extracting data from {len(image_paths)} document images")

            # Get the first image for processing
            image_path = image_paths[0]
            logger.debug(f"Using image: {image_path}")

            # Use the provided document-specific prompt
            logger.debug(f"Using prompt: {prompt}")

            try:
                # Check if file exists before uploading
                if not os.path.exists(image_path):
                    logger.error(f"Image file does not exist: {image_path}")
                    raise VisionParsingError(f"Image file does not exist: {image_path}")

                logger.debug(f"Uploading file: {image_path}")
                # Upload the image file
                files = [self.client.files.upload(file=image_path)]
                logger.debug(f"File uploaded successfully: {files[0].uri}")

                # Create content structure that works with the API
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=files[0].uri,
                                mime_type=files[0].mime_type,
                            ),
                            types.Part.from_text(
                                text=f"{prompt}\n\nReturn ONLY a JSON object with these fields as keys. If any field is not found in the image, set its value to null."
                            ),
                        ],
                    ),
                    # Remove the empty model parts that's causing the error
                    # Add a second user message to trigger the response
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text="Please extract the information as valid JSON only"
                            ),
                        ],
                    ),
                ]

                # Get model from config
                config = self.config_manager.get_config()
                vision_config = config.get("vision", {})
                model = vision_config.get("model", "gemini-2.0-flash")

                # Configure exactly as in the Google example
                generate_config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                )

                # Use non-streaming API
                logger.debug(f"Calling Gemini API with model: {model}")
                response_text = ""

                try:
                    # Use non-streaming generate_content method
                    logger.debug("Making non-streaming API call")
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=generate_config,
                    )
                    response_text = response.text
                    logger.debug("API call successful")

                except Exception as api_error:
                    logger.error(f"API call failed: {str(api_error)}")
                    logger.error(f"Error traceback: {traceback.format_exc()}")
                    return {}

                # If we got here with empty response_text, all attempts failed
                if not response_text:
                    logger.warning("No response text received after all attempts")
                    return {}

                logger.debug(f"Full API response: {response_text}")

                # Parse the JSON response
                try:
                    # Clean the response text before parsing
                    cleaned_response = response_text.strip()

                    # Remove ```json and ``` markers if present (common in LLM responses)
                    if cleaned_response.startswith("```"):
                        # Find the first newline to skip the ```json line
                        first_newline = cleaned_response.find("\n")
                        if first_newline != -1:
                            # Find the last ``` to remove the closing backticks
                            last_backticks = cleaned_response.rfind("```")
                            if last_backticks != -1 and last_backticks > first_newline:
                                cleaned_response = cleaned_response[
                                    first_newline:last_backticks
                                ].strip()
                            else:
                                cleaned_response = cleaned_response[
                                    first_newline:
                                ].strip()

                    logger.debug(f"Cleaned response for parsing: {cleaned_response}")

                    # Try multiple parsing approaches
                    parsed_data = None
                    parsing_errors = []

                    # Approach 1: Direct JSON parsing
                    try:
                        parsed_data = json.loads(cleaned_response)
                        logger.debug("Successfully parsed JSON directly")
                    except json.JSONDecodeError as e:
                        parsing_errors.append(f"Direct parsing error: {str(e)}")

                        # Approach 2: Try to fix common JSON issues
                        try:
                            # Sometimes the response has unescaped newlines or other characters in strings
                            # Try to fix by replacing single quotes with double quotes (if that's the issue)
                            if "'" in cleaned_response and '"' not in cleaned_response:
                                fixed_json = cleaned_response.replace("'", '"')
                                parsed_data = json.loads(fixed_json)
                                logger.debug(
                                    "Successfully parsed JSON after replacing single quotes"
                                )
                        except json.JSONDecodeError as e:
                            parsing_errors.append(
                                f"Quote replacement parsing error: {str(e)}"
                            )

                            # Approach 3: Extract JSON object using regex
                            try:
                                json_match = re.search(
                                    r"\{.*\}", cleaned_response, re.DOTALL
                                )
                                if json_match:
                                    potential_json = json_match.group(0)
                                    logger.debug(
                                        f"Trying to parse extracted JSON: {potential_json}"
                                    )
                                    parsed_data = json.loads(potential_json)
                                    logger.debug(
                                        "Successfully parsed JSON using regex extraction"
                                    )
                                else:
                                    parsing_errors.append(
                                        "No JSON object pattern found in response"
                                    )
                            except Exception as regex_error:
                                parsing_errors.append(
                                    f"Regex extraction error: {str(regex_error)}"
                                )

                    # If all parsing attempts failed
                    if parsed_data is None:
                        logger.error(
                            f"All JSON parsing attempts failed: {', '.join(parsing_errors)}"
                        )
                        logger.debug("Returning empty dictionary")
                        return {}

                    # Ensure the result is a dictionary
                    if isinstance(parsed_data, dict):
                        logger.debug(
                            f"Successfully parsed JSON object: {json.dumps(parsed_data, indent=2)}"
                        )
                        return parsed_data
                    elif isinstance(parsed_data, list):
                        logger.warning(
                            f"API returned a JSON array, expected object: {parsed_data}"
                        )
                        # Handle list case: take the first element if it's a dict
                        if parsed_data and isinstance(parsed_data[0], dict):
                            logger.debug(
                                "Using the first dictionary found in the array."
                            )
                            return parsed_data[0]
                        else:
                            logger.warning(
                                "Returning empty dictionary as API returned unexpected list format."
                            )
                            return {}  # Return empty dict if list or list[0] is not dict
                    else:
                        logger.warning(
                            f"API returned unexpected JSON type: {type(parsed_data)}"
                        )
                        return {}  # Return empty dict for other unexpected types

                except Exception as e:
                    logger.error(f"Unexpected error during JSON parsing: {str(e)}")
                    logger.error(f"Error traceback: {traceback.format_exc()}")
                    return {}  # Return empty dict on any unexpected error

            except Exception as e:
                logger.error(f"Error during Gemini API call: {str(e)}")
                logger.error(f"Error traceback: {traceback.format_exc()}")
                return {}
        except Exception as e:
            logger.error(f"Error extracting document data: {str(e)}")
            logger.error(f"Error traceback: {traceback.format_exc()}")
            return {}


class FuzzyMatcher:
    """General purpose fuzzy matching utility class for matching strings against existing entries.

    This utility class provides fuzzy string matching functionality used throughout the application
    for matching suppliers, invoice numbers, and potentially other data points. It uses
    Python's difflib.SequenceMatcher for calculating string similarity with additional
    bonuses for prefix matches.

    It replaces multiple redundant implementations of fuzzy matching in the codebase,
    offering a single consistent approach to string similarity matching.

    Usage examples:
    - Supplier name matching during vision preprocessing
    - Invoice number matching when populating filter fields
    - Can be extended for other fuzzy matching needs
    """

    def __init__(self, config_manager, excel_manager=None):
        """Initialize the fuzzy matcher with configuration.

        Args:
            config_manager: The application configuration manager
            excel_manager: Optional ExcelManager instance to reuse
        """
        self.config_manager = config_manager
        self.excel_manager = excel_manager  # Reuse existing ExcelManager if provided
        self.entries = {}  # Dictionary to store different types of entries
        self.threshold = 0.7  # Default threshold

    def load_entries(self, entry_type: str, values: list) -> None:
        """Load entries of a specific type.

        Args:
            entry_type: The type of entries (e.g., 'supplier', 'invoice')
            values: List of values to match against
        """
        self.entries[entry_type] = [str(s).strip() for s in values if str(s).strip()]
        logger = get_logger()
        logger.debug(f"Loaded {len(self.entries[entry_type])} {entry_type} entries")
        logger.debug(
            f"Sample {entry_type} entries: {self.entries[entry_type][:5] if len(self.entries[entry_type]) > 5 else self.entries[entry_type]}"
        )

    def load_entries_from_excel(self, entry_type: str, column_name: str) -> None:
        """Load entries from Excel data.

        Args:
            entry_type: The type of entries (e.g., 'supplier', 'invoice')
            column_name: The Excel column name containing the values
        """
        logger = get_logger()
        try:
            config = self.config_manager.get_config()
            if not config.get("excel_file") or not config.get("excel_sheet"):
                logger.debug("Excel configuration not found")
                return

            # Use provided ExcelManager if available, otherwise create new one
            if self.excel_manager:
                excel_manager = self.excel_manager
                logger.debug("Using provided ExcelManager instance")
            else:
                excel_manager = ExcelManager()
                logger.debug("Creating new ExcelManager instance")
                # Load Excel data
                excel_manager.load_excel_data(config["excel_file"], config["excel_sheet"])
            
            if excel_manager.excel_data is None:
                logger.debug("Failed to load Excel data")
                return

            # Get unique values from the specified column
            if column_name in excel_manager.excel_data.columns:
                values = excel_manager.excel_data[column_name].unique().tolist()
                self.load_entries(entry_type, values)
            else:
                logger.warning(f"Column '{column_name}' not found in Excel")

        except Exception as e:
            logger.error(f"Error loading entries from Excel: {str(e)}")
            logger.error(f"Error traceback: {traceback.format_exc()}")

    def find_match(
        self, query: str, entry_type: str, threshold: float = None
    ) -> Dict[str, Any]:
        """Find the best match for a query string among entries of a specific type.

        Args:
            query: The string to match
            entry_type: The type of entries to match against
            threshold: Optional threshold to override the default

        Returns:
            Dictionary with match results
        """
        logger = get_logger()
        logger.debug(
            f"Starting fuzzy matching for '{query}' against {entry_type} entries"
        )

        # Get the entries for the specified type
        values = self.entries.get(entry_type, [])

        if not query or not values:
            logger.debug("Empty query or no entries available")
            return {
                "match_found": False,
                "best_match": None,
                "confidence": 0,
                "original": query,
            }

        # Use the specified threshold or get from config
        if threshold is None:
            config = self.config_manager.get_config()
            vision_config = config.get("vision", {})
            field_threshold_key = f"{entry_type}_match_threshold"
            threshold = vision_config.get(field_threshold_key, self.threshold)

        logger.debug(f"Using match threshold: {threshold}")
        logger.debug(f"Comparing against {len(values)} {entry_type} entries")

        # Find the best match
        best_match, highest_score, matches = self._find_best_match(
            query, values, entry_type
        )

        # Sort matches by score for debugging
        matches.sort(key=lambda x: x[1], reverse=True)
        top_matches = matches[:5] if len(matches) >= 5 else matches
        logger.debug(f"Top matches: {top_matches}")

        match_found = highest_score >= threshold

        result = {
            "match_found": match_found,
            "best_match": best_match,
            "confidence": highest_score,
            "original": query,
            "threshold": threshold,
        }

        logger.debug(f"Fuzzy matching result: {result}")
        return result

    def _parse_formatted_value(self, formatted_value: str) -> str:
        """Parse formatted values that may contain Excel row information.

        This handles values that might have been formatted with row information like:
        "value ⟨Excel Row: 42⟩" or "✓ value ⟨Excel Row: 42⟩"

        Args:
            formatted_value: The formatted value string

        Returns:
            The clean value without formatting
        """
        if not formatted_value:
            return ""

        # Remove checkmark if present
        formatted_value = formatted_value.replace("✓ ", "", 1)

        # Extract the actual value without row info
        match = re.match(r"(.*?)\s*⟨Excel Row:\s*\d+⟩", formatted_value)
        if match:
            return match.group(1).strip()

        return formatted_value.strip()

    def _find_best_match(self, query: str, values: list, entry_type: str) -> tuple:
        """Find the best match for a query among a list of values.

        Args:
            query: The string to match
            values: List of values to match against
            entry_type: The type of entries being matched

        Returns:
            Tuple of (best_match, highest_score, all_matches)
        """
        query = str(query).strip().lower()
        best_match = None
        highest_score = 0
        matches = []

        for value in values:
            value_str = str(value).strip()

            # For invoice values, we need to clean them from any Excel row formatting
            if entry_type == "invoice":
                clean_value = self._parse_formatted_value(value_str).lower()
            else:
                clean_value = value_str.lower()

            # Calculate similarity score using SequenceMatcher
            score = SequenceMatcher(None, query, clean_value).ratio()

            # Apply bonuses for special match cases
            if clean_value.startswith(query) or query.startswith(clean_value):
                score += 0.1  # Bonus for prefix match

            matches.append((value_str, score))
            if score > highest_score:
                highest_score = score
                best_match = value_str

        return best_match, highest_score, matches
