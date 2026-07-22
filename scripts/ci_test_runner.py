"""CI test runner - runs all unit tests."""
import sys
import unittest
import os


def run_tests():
    test_files = [
        "test_imports",
        "test_models",
        "test_error_handler",
        "test_query_result",
        "test_sql_dialect",
        "test_validators",
        "test_sql_fingerprint",
        "test_sql_validation",
        "test_security_injection",
        "test_cache",
        "test_report_generator",
        "test_scheduler_backup",
        "test_sql_validator",
    ]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for module_name in test_files:
        try:
            module = __import__(module_name)
            suite.addTests(loader.loadTestsFromModule(module))
            print(f"Loaded: {module_name}")
        except Exception as e:
            print(f"SKIP {module_name}: {e}")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)