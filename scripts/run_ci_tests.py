"""
CI test runner - bypasses pytest to avoid plugin conflicts
"""
import sys
import unittest

# Test modules to run
TEST_MODULES = [
    "tests.test_imports",
    "tests.test_models",
    "tests.test_error_handler",
    "tests.test_query_result",
    "tests.test_sql_dialect",
    "tests.test_validators",
    "tests.test_sql_fingerprint",
    "tests.test_sql_validation",
    "tests.test_security_injection",
    "tests.test_cache",
    "tests.test_report_generator",
    "tests.test_scheduler_backup",
    "tests.test_sql_validator",
]

# Add all unit test modules
import os
unit_dir = os.path.join(os.path.dirname(__file__), "tests", "unit")
for root, dirs, files in os.walk(unit_dir):
    for f in files:
        if f.endswith(".py") and not f.startswith("__"):
            rel_path = os.path.relpath(os.path.join(root, f), os.path.dirname(__file__))
            module_name = rel_path.replace(os.sep, ".")[:-3]
            if module_name not in TEST_MODULES:
                TEST_MODULES.append(module_name)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    for module_name in TEST_MODULES:
        try:
            module = __import__(module_name, fromlist=[""])
            tests = loader.loadTestsFromModule(module)
            suite.addTests(tests)
            print(f"Loaded: {module_name}")
        except Exception as e:
            print(f"SKIP {module_name}: {e}")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)