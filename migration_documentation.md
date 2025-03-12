# Tkinter to PyQt6 Migration Documentation

## Technical Analysis of Tkinter Application

(Content from technical_analysis_plan.md)

## Detailed Technical Analysis Plan for Tkinter Application

**Phase 1: Information Gathering and Understanding**

1.  **Explore Project Structure:** List files in the current directory to understand the project layout.
    - Tool: `list_files`

2.  **Examine `main.py`:** Read the main application file to understand the application's entry point and overall structure.
    - Tool: `read_file`

3.  **Investigate UI Files:** Read UI files (`src/ui/*.py`) to understand UI components and structure.
    - Tool: `read_file`
    - Focus on:
        - `config_tab.py`: Configuration settings for source folder, Excel file, and filters.
        - `processing_tab.py`: Main processing logic, PDF display, and filter interaction.

4.  **Analyze Utility Files:** Examine utility files (`src/utils/*.py`) to understand data model and core logic.
    - Tool: `read_file`
    - Focus on:
        - `config_manager.py`: Loading, saving, and managing configuration settings.
        - `excel_manager.py`: Excel file operations, data loading, and hyperlink management.
        - `pdf_manager.py`: PDF processing, file handling, and rotation.
        - `template_manager.py`: Template parsing and processing for output file naming.
        - `models.py`: Data models, specifically the `PDFTask` class.

5.  **Clarifying Questions:** Ask the user clarifying questions to ensure complete understanding.
    - Tool: `ask_followup_question`
    - Questions:
        - What is the primary purpose of the File Organizer application?
        - What specific types of files does it process, and what is the expected output?
        - Is there a specific reason for migrating to PyQt6, such as performance improvements, cross-platform compatibility, or access to specific PyQt6 features?
        - Does the application support updating existing data in a row?

**Phase 2: Detailed Analysis and Documentation Plan**

6.  **Detailed Analysis Plan Creation:** Create a detailed plan for technical analysis. (This step - Architect mode)

7.  **User Review and Approval of Analysis Plan:** Get user approval for the analysis plan.
    - Tool: `ask_followup_question`

8.  **PyQt6 Migration Plan Development:** Develop a comprehensive PyQt6 migration plan. (Next phase - Architect mode)

9.  **User Review and Approval of Migration Plan:** Get user approval for the migration plan.
    - Tool: `ask_followup_question`

10. **Plan Documentation:** Write the analysis and migration plans to a markdown file.
    - Tool: `write_to_file`

11. **Mode Switch Request:** Request to switch to Code mode for implementation.
    - Tool: `switch_mode`

**Detailed Analysis Steps:**

1.  **Execution Flow Analysis**: Trace application startup, main loop, and shutdown. (Tools: `read_file`)
    - Focus on `main.py` and the initialization of UI components and managers.

2.  **Technical Architecture Documentation**: Document modular structure and class relationships. (Tools: `list_code_definition_names`, `read_file`)
    - Use `list_code_definition_names` to identify classes and functions in each module.
    - Use `read_file` to examine class relationships and dependencies.

3.  **Core Functionality Definition**: Define primary purpose and core features. (Method: Code review and task description review)
    - Focus on data entry, linking PDFs, and updating Excel.

4.  **Event-Driven Interactions Analysis**: Trace event flow, data transformations, and UI state changes for user interactions. (Tools: `read_file`)
    - Focus on button clicks, combobox selections, and filter updates in `config_tab.py` and `processing_tab.py`.

5.  **Data Model Documentation**: Detail data structures, persistence mechanisms, and data flow. (Tools: `read_file`)
    - Focus on the `PDFTask` class in `models.py` and data handling in `excel_manager.py` and `config_manager.py`.

6.  **UI State Management Strategy**: Describe UI state management and update mechanisms. (Method: Code review)
    - Focus on how UI elements are updated in response to configuration changes and data loading.

7.  **Validation Rules Documentation**: Document input validation rules, triggers, and errors. (Tools: `search_files`, Code review)
    - Use `search_files` to find validation logic in `config_tab.py` and `processing_tab.py`.

8.  **I/O Operations and External Dependencies**: Document file I/O, external libraries, and network calls. (Tools: `search_files`, Code review)
    - Use `search_files` to identify file I/O operations and external library usage in `excel_manager.py` and `pdf_manager.py`.

9.  **Layout Management and UI Hierarchy**: Describe layout strategy and widget hierarchy. (Tools: `read_file`)
    - Focus on the use of `grid` and other layout managers in `config_tab.py` and `processing_tab.py`.

10. **Conceptual Model Construction**: Synthesize analysis into a conceptual model with diagrams and explanations. (Method: Documentation consolidation and diagram creation)

## PyQt6 Migration Plan

(Content from PYQT6_migration_plan.md)

**Phase 3: PyQt6 Migration Plan Development**

1.  **Project Structure:**
    -   Create a new directory structure within the existing `PYQT6/` directory.
    -   `PYQT6/`: Root directory for the PyQt6 application.
        -   `main.py`: Entry point for the PyQt6 application.
        -   `src/`: Source code directory.
            -   `ui/`: UI-related modules.
                -   `config_tab.py`: PyQt6 implementation of the configuration tab.
                -   `processing_tab.py`: PyQt6 implementation of the processing tab.
                -   `fuzzy_search.py`: PyQt6 implementation of the fuzzy search functionality.
                -   `widgets.py`: Custom widgets for the application.
            -   `utils/`: Utility modules.
                -   `config_manager.py`: PyQt6-compatible configuration management.
                -   `excel_manager.py`: PyQt6-compatible Excel data handling.
                -   `pdf_manager.py`: PyQt6-compatible PDF processing.
                -   `template_manager.py`: PyQt6-compatible template processing.
            -   `models.py`: Data models (if needed, adapt from Tkinter).

2.  **Component Breakdown and Mapping:**
    -   **MainWindow (`main.py`):**
        -   Tkinter `Tk` -> PyQt6 `QMainWindow`.
        -   Tkinter `Notebook` -> PyQt6 `QTabWidget`.
        -   Status bar: Tkinter `Label` -> PyQt6 `QStatusBar`.
    -   **ConfigTab (`src/ui/config_tab.py`):**
        -   Tkinter `Frame` -> PyQt6 `QWidget` (within a `QScrollArea`).
        -   Tkinter `Label` -> PyQt6 `QLabel`.
        -   Tkinter `Entry` -> PyQt6 `QLineEdit`.
        -   Tkinter `Button` -> PyQt6 `QPushButton`.
        -   Tkinter `Combobox` -> PyQt6 `QComboBox`.
        -   Tkinter `filedialog.askdirectory` -> PyQt6 `QFileDialog.getExistingDirectory`.
        -   Tkinter `filedialog.askopenfilename` -> PyQt6 `QFileDialog.getOpenFileName`.
    -   **ProcessingTab (`src/ui/processing_tab.py`):**
        -   Tkinter `Frame` -> PyQt6 `QWidget`.
        -   PDF Viewer: Implement using `QPdfView` or render pages to `QPixmap` in a `QLabel`.
        -   Queue Display: Tkinter `Treeview` -> PyQt6 `QTableView` with a custom `QAbstractTableModel`.
        -   Filters: Tkinter `Entry` + Fuzzy Search -> PyQt6 `QLineEdit` + custom filtering logic.
        -   **Second Filter Parsing:**
            -   The `_parse_filter2_value` method in `ProcessingQueue` extracts the original value and row number from a formatted string ("✓ value ⟨Excel Row: N⟩").
            -   This method should be implemented in a PyQt6-compatible class (either in `src/utils/` or `src/ui/`).
            -   The method should take the formatted string as input and return a tuple containing the original value and row number.
            -   The `_on_filter_select` method in `ProcessingTab` uses the parsed row index to filter the Excel data. This logic should be adapted to PyQt6.
            -   The `_format_filter2_value` method in `ProcessingTab` formats the filter2 value with the row number and hyperlink status. This formatting logic should also be preserved in the PyQt6 implementation.
        -   **Processing Queue, Task Atomicity, and Reversal:**
            -   **Processing Queue:**
                -   Tkinter `Dict[str, PDFTask]` -> PyQt6 `QHash` or Python dictionary.
                -   `threading.Thread` and `threading.Lock` -> `QThread` and `QMutex` (or `QReadWriteLock`).
                -   Callbacks -> PyQt6 signals and slots.
            -   **Task Atomicity:**
                -   `TemporaryDirectory` context manager can be used directly in PyQt6.
                -   File operations (copying, rotating, moving, removing) -> Qt-compatible methods (e.g., `QFile::copy`, `QFile::rename`, `QFile::remove`).
                -   Wrap file operations in try-except blocks.
                -   Consider using transactions for more complex operations.
            -   **Task Reversal:**
                -   Preserve the original hyperlink before updating it.
                -   Adapt the `revert_pdf_link` method to use PyQt6-compatible libraries and methods for updating the Excel file.
                -   Implement the logic for reverting a task in the PyQt6 application.
    -   **FuzzySearchFrame (`src/ui/fuzzy_search.py`):**
        -   Tkinter `Frame` -> PyQt6 `QWidget`.
        -   Tkinter `Entry` -> PyQt6 `QLineEdit`.
        -   Tkinter `Listbox` -> PyQt6 `QListWidget`.
        -   Implement fuzzy search logic using `difflib.SequenceMatcher` or a similar algorithm.
        -   **Migration Considerations:**
            -   Adapt event handling to use PyQt6 signals and slots.
            -   Preserve the fuzzy matching logic (including bonuses for exact/prefix matches).
            -   Use `QLineEdit.setPlaceholderText` for placeholder text.
            -   Adapt keyboard navigation logic.
            -   Use `QListWidget`'s built-in mousewheel scrolling.
            -   Use `QMenu` for the context menu.
            -   Adapt hyperlink handling logic.
            -   Replace Tkinter styling with PyQt6 stylesheets or widget properties.

    -   **Data Models (`src/models.py`):**
        -   Adapt Tkinter `dataclass` to standard Python classes if necessary.

3.  **Data Flow and Signals/Slots:**
    -   Configuration changes in `ConfigTab` should emit signals to update the `ProcessingTab`.
    -   Excel data loading should emit signals to update filter options in `ProcessingTab`.
    -   PDF processing tasks should emit signals to update the queue display.
    -   Use PyQt6 signals and slots for communication between UI components and background tasks.

4.  **State Management:**
    -   If necessary, implement a state management pattern (e.g., using `QSettings` for persistent settings or a custom state class).

5.  **Code Adaptation:**
    -   Adapt variable names and class names to follow PyQt6 conventions (e.g., `source_folder_entry` -> `source_folder_line_edit`).
    -   Use PyQt6-idiomatic code for UI updates and event handling.
    -   Prioritize maintainability and readability over direct code translation.

6.  **User Input and Validation:**
    -   Use `QLineEdit` for text input with appropriate validators (`QIntValidator`, `QDoubleValidator`, `QRegExpValidator`).
    -   Implement custom validation logic using PyQt6 signals and slots.
    -   Provide clear error messages using `QMessageBox`.

7.  **Data Processing:**
    -   Adapt Excel data loading and manipulation logic to use PyQt6-compatible libraries (e.g., `pandas` with `xlsxwriter`).
    -   Use PyQt6 data structures (`QList`, `QMap`) for data storage and manipulation if necessary.

8.  **Output Display:**
    -   Use `QLabel` to display PDF pages (rendered as `QPixmap`).
    -   Use `QTableView` with a custom `QAbstractTableModel` to display the processing queue.

9.  **Error Handling:**
    -   Use `QMessageBox` to display error messages.
    -   Log errors to a file or console for debugging.

10. **Migration Steps:**
    1.  Create the basic PyQt6 project structure.
    2.  Implement the `MainWindow` with basic UI elements.
    3.  Migrate the `ConfigTab` UI and functionality.
    4.  Migrate the `ProcessingTab` UI and functionality, including the second filter parsing logic and processing queue management.
    5.  Adapt the `FuzzySearchFrame` to PyQt6.
    6.  Adapt the utility modules to be PyQt6-compatible.
    7.  Implement data flow and signal/slot connections.
    8.  Implement state management (if necessary).
    9.  Test and debug the PyQt6 application.