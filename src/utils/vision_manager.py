from __future__ import annotations
from typing import Dict, Any, Optional, List
import os
import json
import re
from datetime import datetime

from google import genai
from google.genai import types


class VisionParsingError(Exception):
    """Exception raised for errors in the vision preprocessing process."""

    pass


class VisionManager:
    """Manager for vision-related preprocessing operations.

    This class handles all vision preprocessing functionality used for filter auto-population,
    keeping it separate from the PDF processing workflow.
    """

    def __init__(self, config_manager):
        """Initialize the Vision Manager.

        Args:
            config_manager: The application configuration manager
        """
        self.config_manager = config_manager
        self._vision_parser = None
        self._initialize_vision_service()

    def _initialize_vision_service(self):
        """Initialize the vision parser service."""
        if self.config_manager:
            self._vision_parser = VisionParserService(self.config_manager)
            print("[DEBUG] Vision preprocessing service initialized")
        else:
            print(
                "[DEBUG] Cannot initialize vision service - no config manager provided"
            )

    def preprocess_pdf(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Run vision preprocessing on a PDF to extract data for filter population.

        This function handles preprocessing PDFs to extract data that can be used
        to auto-populate filter fields in the UI, completely separate from the
        actual PDF processing workflow.

        Args:
            pdf_path: Path to the PDF file to preprocess

        Returns:
            Optional[Dict[str, Any]]: Vision preprocessing results or None if failed
        """
        if not self._vision_parser:
            print(
                "[DEBUG] Vision preprocessing not available - service not initialized"
            )
            return None

        config = self.config_manager.get_config()
        vision_config = config.get("vision", {})

        if not vision_config.get("enabled", False):
            print("[DEBUG] Vision preprocessing is disabled in config")
            return None

        try:
            print(f"[DEBUG] Running vision preprocessing on {pdf_path}")
            vision_result = self._vision_parser.process_invoice(pdf_path)
            print("[DEBUG] Vision preprocessing completed successfully")
            return vision_result
        except VisionParsingError as e:
            print(f"[DEBUG] Vision preprocessing error: {str(e)}")
            return None
        except Exception as e:
            print(f"[DEBUG] Unexpected vision preprocessing error: {str(e)}")
            return None

    def is_vision_enabled(self) -> bool:
        """Check if vision preprocessing is enabled in the configuration.

        Returns:
            bool: True if vision preprocessing is enabled, False otherwise
        """
        if not self.config_manager:
            return False

        config = self.config_manager.get_config()
        vision_config = config.get("vision", {})
        return vision_config.get("enabled", False)

    def has_vision_service(self) -> bool:
        """Check if the vision service is available.

        Returns:
            bool: True if vision service is available, False otherwise
        """
        return self._vision_parser is not None


class VisionParserService:
    """Service for extracting information from scanned invoices using Google Gemini API for filter preprocessing."""

    def __init__(self, config_manager):
        """Initialize the vision preprocessing service with configuration.

        Args:
            config_manager: The application configuration manager
        """
        self.config_manager = config_manager
        self._init_gemini_client()
        self._fuzzy_matcher = FuzzyMatcher(config_manager)

        # Load suppliers for fuzzy matching
        suppliers_column = config_manager.get_config().get(
            "filter1_column", "FOURNISSEURS"
        )
        self._fuzzy_matcher.load_entries_from_excel("supplier", suppliers_column)

    def _init_gemini_client(self) -> None:
        """Initialize the Gemini API client."""
        config = self.config_manager.get_config()
        api_key = os.environ.get("GEMINI_API_KEY")

        # Check if API key is available
        if not api_key:
            print("[DEBUG] Gemini API key not found in environment variables")
            # Try to get from config
            vision_config = config.get("vision", {})
            api_key = vision_config.get("gemini_api_key")
            if not api_key:
                print("[DEBUG] Gemini API key not found in config")

        if api_key:
            self.client = genai.Client(api_key=api_key)
            print("[DEBUG] Gemini API client initialized successfully")
        else:
            print(
                "[DEBUG] WARNING: No Gemini API key found, vision preprocessing will be disabled"
            )
            self.client = None

    def process_invoice(self, pdf_path: str) -> Dict[str, Any]:
        """Preprocess a PDF invoice using vision AI to extract data for filter population.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dict containing extracted invoice data for filter population

        Raises:
            VisionParsingError: If preprocessing fails
        """
        try:
            print(f"[DEBUG] Starting vision preprocessing for invoice: {pdf_path}")

            # Check configuration for vision preprocessing
            config = self.config_manager.get_config()
            vision_config = config.get("vision", {})
            print(
                f"[DEBUG] Vision preprocessing config: {json.dumps(vision_config, indent=2)}"
            )

            # Step 1: Convert PDF to images
            print("[DEBUG] Converting PDF to images...")
            image_paths = self._convert_pdf_to_images(pdf_path)
            if not image_paths:
                print("[DEBUG] Failed to convert PDF to images")
                raise VisionParsingError("Failed to convert PDF to images")
            print(f"[DEBUG] Generated {len(image_paths)} images from PDF")

            # Step 2: Extract text using Gemini Vision API
            print("[DEBUG] Extracting data from images with Gemini...")
            extracted_data = self._extract_invoice_data(image_paths)
            print(
                f"[DEBUG] Extracted data for filter population: {json.dumps(extracted_data, indent=2)}"
            )

            # Step 3: Validate supplier with fuzzy matching
            supplier_name = extracted_data.get("supplier_name", "")
            print(f"[DEBUG] Validating extracted supplier name: '{supplier_name}'")
            supplier_validation = self._fuzzy_matcher.find_match(
                supplier_name, "supplier"
            )
            print(
                f"[DEBUG] Supplier validation result: {json.dumps(supplier_validation, indent=2)}"
            )

            # Combine results
            result = {
                "extracted_data": extracted_data,
                "supplier_validation": supplier_validation,
                "validation_status": "validated"
                if supplier_validation["match_found"]
                else "needs_review",
                "confidence_score": supplier_validation.get("confidence", 0),
                "processing_time": datetime.now().isoformat(),
            }

            print(
                f"[DEBUG] Vision preprocessing complete. Final result: {json.dumps(result, indent=2)}"
            )
            return result

        except Exception as e:
            error_msg = f"Vision preprocessing failed: {str(e)}"
            print(f"[DEBUG] {error_msg}")
            import traceback

            print(f"[DEBUG] Error traceback: {traceback.format_exc()}")
            raise VisionParsingError(error_msg)

    def _convert_pdf_to_images(self, pdf_path: str) -> List[str]:
        """Convert PDF pages to images for processing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of paths to generated images
        """
        try:
            # This is a placeholder - in a real implementation, you would use a library like pdf2image
            # For now, we'll assume the conversion works and return a dummy path
            print(f"[DEBUG] Converting PDF to images: {pdf_path}")

            # In a real implementation:
            # from pdf2image import convert_from_path
            # images = convert_from_path(pdf_path)
            # image_paths = []
            # for i, image in enumerate(images):
            #     img_path = f"{pdf_path}_page_{i}.jpg"
            #     image.save(img_path, "JPEG")
            #     image_paths.append(img_path)

            # For now, just return the PDF path as a placeholder
            print(
                "[DEBUG] Using PDF path directly as image path (placeholder implementation)"
            )
            return [pdf_path]
        except Exception as e:
            print(f"[DEBUG] Error converting PDF to images: {str(e)}")
            import traceback

            print(f"[DEBUG] Error traceback: {traceback.format_exc()}")
            return []

    def _extract_invoice_data(self, image_paths: List[str]) -> Dict[str, Any]:
        """Extract invoice data from images using Gemini Vision API.

        Args:
            image_paths: List of image paths to process

        Returns:
            Structured data extracted from the invoice
        """
        try:
            if not self.client:
                print(
                    "[DEBUG] Cannot extract invoice data - Gemini client not initialized"
                )
                raise VisionParsingError("Gemini client not initialized")

            print(f"[DEBUG] Extracting data from {len(image_paths)} invoice images")

            # Get the first image for processing
            image_path = image_paths[0]
            print(f"[DEBUG] Using image: {image_path}")

            # Define the prompt for invoice data extraction
            prompt = """
            Extract the following information from this scanned invoice:
            1. Supplier/Vendor Name
            2. Invoice Number
            3. Invoice Date (in format DD/MM/YYYY)
            4. Total Amount (with currency)
            
            Return ONLY a JSON object with these fields as keys:
            {
                "supplier_name": "extracted supplier name",
                "invoice_number": "extracted invoice number",
                "invoice_date": "extracted date in DD/MM/YYYY format",
                "total_amount": "extracted amount with currency"
            }
            
            If any field is not found in the image, set its value to null.
            """
            print(f"[DEBUG] Using prompt: {prompt}")

            try:
                # Check if file exists before uploading
                if not os.path.exists(image_path):
                    print(f"[DEBUG] Image file does not exist: {image_path}")
                    raise VisionParsingError(f"Image file does not exist: {image_path}")

                print(f"[DEBUG] Uploading file: {image_path}")
                # Upload the image file
                files = [self.client.files.upload(file=image_path)]
                print(f"[DEBUG] File uploaded successfully: {files[0].uri}")

                # Create content with image and prompt
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=files[0].uri,
                                mime_type=files[0].mime_type,
                            ),
                            types.Part.from_text(text=prompt),
                        ],
                    ),
                ]

                # Configure the generation parameters
                generate_config = types.GenerateContentConfig(
                    temperature=0.5,  # Lower temperature for more focused extraction
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                    response_mime_type="text/plain",  # Changed to text/plain as per example
                )

                # Process the image with streaming
                response_text = ""
                model = "gemini-2.0-flash"
                print(f"[DEBUG] Calling Gemini API with model: {model}")

                for chunk in self.client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=generate_config,
                ):
                    response_text += chunk.text
                    print(f"[DEBUG] Received text chunk from API")

                print(f"[DEBUG] Full API response: {response_text}")

                # Parse the JSON response
                try:
                    # Clean the response text before parsing
                    cleaned_response = response_text.strip()
                    # Remove ```json and ``` markers if present
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

                    print(f"[DEBUG] Cleaned response for parsing: {cleaned_response}")
                    result = json.loads(cleaned_response)
                    print(
                        f"[DEBUG] Successfully parsed JSON response: {json.dumps(result, indent=2)}"
                    )
                    return result
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] Failed to parse JSON response: {response_text}")
                    print(f"[DEBUG] JSON parse error: {str(e)}")
                    # Try to extract JSON from the response if it contains other text
                    try:
                        # Look for JSON object in the text
                        json_match = re.search(
                            r"({[^{}]*({[^{}]*})*[^{}]*})", response_text
                        )
                        if json_match:
                            potential_json = json_match.group(1)
                            print(
                                f"[DEBUG] Trying to parse extracted JSON: {potential_json}"
                            )
                            result = json.loads(potential_json)
                            print(
                                f"[DEBUG] Successfully parsed extracted JSON: {json.dumps(result, indent=2)}"
                            )
                            return result
                    except Exception as json_extract_error:
                        print(
                            f"[DEBUG] Failed to extract JSON from response: {str(json_extract_error)}"
                        )

                    # If all parsing attempts fail, return empty object
                    return {
                        "supplier_name": None,
                        "invoice_number": None,
                        "invoice_date": None,
                        "total_amount": None,
                    }

            except Exception as e:
                print(f"[DEBUG] Error during Gemini API call: {str(e)}")
                import traceback

                print(f"[DEBUG] Error traceback: {traceback.format_exc()}")
                return {
                    "supplier_name": None,
                    "invoice_number": None,
                    "invoice_date": None,
                    "total_amount": None,
                }
        except Exception as e:
            print(f"[DEBUG] Error extracting invoice data: {str(e)}")
            import traceback

            print(f"[DEBUG] Error traceback: {traceback.format_exc()}")
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

    def __init__(self, config_manager):
        """Initialize the fuzzy matcher with configuration.

        Args:
            config_manager: The application configuration manager
        """
        self.config_manager = config_manager
        self.entries = {}  # Dictionary to store different types of entries
        self.threshold = 0.7  # Default threshold

    def load_entries(self, entry_type: str, values: list) -> None:
        """Load entries of a specific type.

        Args:
            entry_type: The type of entries (e.g., 'supplier', 'invoice')
            values: List of values to match against
        """
        self.entries[entry_type] = [str(s).strip() for s in values if str(s).strip()]
        print(f"[DEBUG] Loaded {len(self.entries[entry_type])} {entry_type} entries")
        print(
            f"[DEBUG] Sample {entry_type} entries: {self.entries[entry_type][:5] if len(self.entries[entry_type]) > 5 else self.entries[entry_type]}"
        )

    def load_entries_from_excel(self, entry_type: str, column_name: str) -> None:
        """Load entries from Excel data.

        Args:
            entry_type: The type of entries (e.g., 'supplier', 'invoice')
            column_name: The Excel column name containing the values
        """
        try:
            config = self.config_manager.get_config()
            if not config.get("excel_file") or not config.get("excel_sheet"):
                print("[DEBUG] Excel configuration not found")
                return

            from .excel_manager import ExcelManager

            excel_manager = ExcelManager()

            # Load Excel data
            excel_manager.load_excel_data(config["excel_file"], config["excel_sheet"])
            if excel_manager.excel_data is None:
                print("[DEBUG] Failed to load Excel data")
                return

            # Get unique values from the specified column
            if column_name in excel_manager.excel_data.columns:
                values = excel_manager.excel_data[column_name].unique().tolist()
                self.load_entries(entry_type, values)
            else:
                print(f"[DEBUG] Column '{column_name}' not found in Excel")

        except Exception as e:
            print(f"[DEBUG] Error loading entries from Excel: {str(e)}")
            import traceback

            print(f"[DEBUG] Error traceback: {traceback.format_exc()}")

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
        print(
            f"[DEBUG] Starting fuzzy matching for '{query}' against {entry_type} entries"
        )

        # Get the entries for the specified type
        values = self.entries.get(entry_type, [])

        if not query or not values:
            print("[DEBUG] Empty query or no entries available")
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

        print(f"[DEBUG] Using match threshold: {threshold}")
        print(f"[DEBUG] Comparing against {len(values)} {entry_type} entries")

        # Find the best match
        best_match, highest_score, matches = self._find_best_match(
            query, values, entry_type
        )

        # Sort matches by score for debugging
        matches.sort(key=lambda x: x[1], reverse=True)
        top_matches = matches[:5] if len(matches) >= 5 else matches
        print(f"[DEBUG] Top matches: {top_matches}")

        match_found = highest_score >= threshold

        result = {
            "match_found": match_found,
            "best_match": best_match,
            "confidence": highest_score,
            "original": query,
            "threshold": threshold,
        }

        print(f"[DEBUG] Fuzzy matching result: {result}")
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
        import re

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
        from difflib import SequenceMatcher

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
