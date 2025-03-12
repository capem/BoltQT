## PyQt6 Migration Plan

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