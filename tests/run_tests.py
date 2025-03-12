#!/usr/bin/env python3
import sys
import os
import unittest
from PyQt6.QtWidgets import QApplication

def run_tests():
    """Run all test cases."""
    # Create QApplication instance for GUI tests
    app = QApplication(sys.argv)
    
    # Find and load tests
    test_loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = test_loader.discover(start_dir, pattern="test_*.py")
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Clean up
    app.quit()
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())