# File Organizer (PyQt6 Version)

A GUI application for organizing and processing PDF files with Excel integration.

## Requirements

- Python 3.8 or higher
- PyQt6
- PyMuPDF (fitz)
- pandas
- openpyxl

## Installation

1. Create a Python virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
   - Windows:
     ```bash
     .\venv\Scripts\activate
     ```
   - Linux/macOS:
     ```bash
     source venv/bin/activate
     ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. Configure the application:
   - Set source folder for PDF files
   - Set processed folder for output
   - Select Excel file and sheet
   - Configure filter columns

3. Process files:
   - Load a PDF file
   - Select filter values
   - Click "Process File" to process the current file
   - Click "Skip File" to skip to the next file

## Features

- **PDF Preview**: View PDF files with zoom and rotation controls
- **Fuzzy Search**: Smart filtering with fuzzy matching
- **Excel Integration**: Link processed PDFs in Excel files
- **Processing Queue**: Track file processing status
- **Error Handling**: Clear error messages and recovery options

## Configuration

- **Source Folder**: Where to find input PDF files
- **Processed Folder**: Where to store processed files
- **Excel File**: Excel file for data integration
- **Excel Sheet**: Sheet name containing the data
- **Filter Columns**: Column names for filtering data

## Keyboard Shortcuts

- **Ctrl+N**: Skip to next file
- **Tab**: Move between filters
- **Enter**: Process current file when focused on Process button

## Development

The application uses PyQt6 for the GUI and follows a modular architecture:

- `src/ui/`: User interface components
- `src/utils/`: Utility functions and managers
- `main.py`: Application entry point

## License

This project is licensed under the MIT License.