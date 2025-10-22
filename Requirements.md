pyinstaller --name=BoltQT --windowed --noconfirm --add-data="config.json:." main.py

# Requirements Specification

## 1. Introduction

This document outlines the functional and non-functional requirements for the File Organizer application. The application is a desktop utility designed to help users organize and process PDF files by integrating with an Excel spreadsheet.

## 2. Functional Requirements

### 2.1. User Stories and Acceptance Criteria

#### User Story 1: Configure Application Settings

*   **As a user, I want to configure the source and processed file folders so that I can control where the application reads files from and saves them to.**
*   **Acceptance Criteria:**
    *   The user can select a source folder for PDF files.
    *   The user can select a processed folder for output files.
    *   The selected folders are saved and loaded correctly across application sessions.

#### User Story 2: Configure Excel Integration

*   **As a user, I want to select an Excel file and a specific sheet within it so that I can link the processed PDF files to the correct data.**
*   **Acceptance Criteria:**
    *   The user can select an Excel file.
    *   The user can select a sheet from the chosen Excel file.
    *   The application can read data from the selected Excel sheet.
    *   The selected Excel file and sheet are saved and loaded correctly across application sessions.

#### User Story 3: Configure Filter Columns

*   **As a user, I want to configure the filter columns from the Excel sheet so that I can use them to find and process the correct PDF files.**
*   **Acceptance Criteria:**
    *   The user can select one or more columns from the Excel sheet to use as filters.
    *   The selected filter columns are displayed in the main application window.

#### User Story 4: View and Navigate PDF Files

*   **As a user, I want to view a preview of the PDF files and navigate through them so that I can easily identify the files I need to process.**
*   **Acceptance Criteria:**
    *   The application displays a preview of the current PDF file.
    *   The user can zoom in and out of the PDF preview.
    *   The user can rotate the PDF preview.
    *   The user can navigate to the next and previous PDF files in the source folder.

#### User Story 5: Filter and Process Files

*   **As a user, I want to filter the PDF files based on the configured columns and process them so that I can efficiently organize my files.**
*   **Acceptance Criteria:**
    *   The user can select filter values from dropdown menus corresponding to the configured filter columns.
    *   The application uses fuzzy search to find matching data in the Excel sheet.
    *   The user can click a "Process File" button to process the current file.
    *   Processing the file links the PDF to the corresponding row in the Excel sheet.
    *   The user can click a "Skip File" button to move to the next file without processing the current one.

#### User Story 6: Track File Processing Status

*   **As a user, I want to see the status of the file processing so that I know which files have been processed and which ones are remaining.**
*   **Acceptance Criteria:**
    *   The application displays a queue of files to be processed.
    *   The application indicates the current status of each file (e.g., pending, processed, skipped).

#### User Story 7: Handle Errors Gracefully

*   **As a user, I want to see clear error messages and have options for recovery when something goes wrong so that I can continue my work without frustration.**
*   **Acceptance Criteria:**
    *   The application displays a clear and understandable error message if a file cannot be processed.
    *   The application provides options to retry the operation or skip the file.

## 3. Non-Functional Requirements

### 3.1. Performance

*   The application should load and display PDF files within 2 seconds.
*   The fuzzy search should return results within 1 second for a dataset of up to 10,000 rows.
*   The application should be responsive and not freeze during file processing.

### 3.2. Cross-Platform Compatibility

*   The application should run on Windows, macOS, and Linux.

### 3.3. Offline Use

*   The application should be fully functional without an internet connection.

### 3.4. Installer Size

*   The installer size should be as small as possible, ideally under 50MB.

