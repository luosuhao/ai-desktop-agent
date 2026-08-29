"""
Unit tests for data_processor.py
"""
import os
import sys
import tempfile
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_processor import calculate_average, calculate_stats, save_report, filter_outliers


class TestDataProcessor(unittest.TestCase):

    def test_calculate_average_normal(self):
        self.assertEqual(calculate_average([1, 2, 3, 4, 5]), 3.0)

    def test_calculate_average_single(self):
        self.assertEqual(calculate_average([42]), 42.0)

    # TODO: Add test for calculate_average with empty list

    def test_calculate_stats_normal(self):
        data = [{"score": "85"}, {"score": "92"}, {"score": "78"}]
        result = calculate_stats(data, "score")
        self.assertIsNotNone(result)
        self.assertEqual(result["min"], 78.0)
        self.assertEqual(result["max"], 92.0)
        self.assertEqual(result["count"], 3)

    def test_calculate_stats_missing_column(self):
        data = [{"name": "Alice"}]
        result = calculate_stats(data, "score")
        self.assertIsNone(result)


class TestFilterOutliers(unittest.TestCase):

    def test_filter_outliers_no_outliers(self):
        """Test that data with no outliers is returned unchanged."""
        data = [
            {"name": "A", "value": "10"},
            {"name": "B", "value": "11"},
            {"name": "C", "value": "9"},
        ]
        result = filter_outliers(data, "value", 2.0)
        self.assertEqual(len(result), 3)

    def test_filter_outliers_with_outliers(self):
        """Test that outliers beyond threshold are filtered out."""
        # Values: 10, 12, 8, 9, 5, 11, 7, 500
        # The value 500 is clearly an outlier (> 2 std devs from mean)
        data = [
            {"name": "A", "value": "10"},
            {"name": "B", "value": "12"},
            {"name": "C", "value": "8"},
            {"name": "D", "value": "9"},
            {"name": "E", "value": "5"},
            {"name": "F", "value": "11"},
            {"name": "G", "value": "7"},
            {"name": "H", "value": "500"},  # outlier
        ]
        result = filter_outliers(data, "value", 2.0)
        self.assertEqual(len(result), 7)
        names = [row["name"] for row in result]
        self.assertNotIn("H", names)

    def test_filter_outliers_empty_data(self):
        """Test that empty data returns an empty list."""
        result = filter_outliers([], "value", 2.0)
        self.assertEqual(result, [])

    def test_filter_outliers_all_same_value(self):
        """Test that data with all identical values keeps all rows."""
        data = [
            {"name": "A", "value": "50"},
            {"name": "B", "value": "50"},
            {"name": "C", "value": "50"},
        ]
        result = filter_outliers(data, "value", 2.0)
        self.assertEqual(len(result), 3)

    def test_filter_outliers_missing_column_value(self):
        """Test that rows with missing/invalid column values are kept."""
        data = [
            {"name": "A", "value": "10"},
            {"name": "B", "value": "abc"},  # invalid
            {"name": "C"},                  # missing column
        ]
        result = filter_outliers(data, "value", 2.0)
        self.assertEqual(len(result), 3)

    def test_filter_outliers_tight_threshold(self):
        """Test with a very tight threshold (0.5 std dev)."""
        data = [
            {"name": "A", "value": "10"},
            {"name": "B", "value": "10"},
            {"name": "C", "value": "20"},
        ]
        # Mean = 13.33, std dev ≈ 4.71
        # |10 - 13.33| = 3.33 > 0.5 * 4.71 = 2.36 -> outlier
        # |20 - 13.33| = 6.67 > 0.5 * 4.71 = 2.36 -> outlier
        result = filter_outliers(data, "value", 0.5)
        self.assertEqual(len(result), 0)

    def test_filter_outliers_keeps_non_outliers(self):
        """Test that non-outlier rows are preserved correctly."""
        # Values: 5, 6, 7, 4, 8, 9, 10, 200
        # The value 200 is clearly an outlier (> 2 std devs from mean)
        data = [
            {"name": "A", "value": "5"},
            {"name": "B", "value": "6"},
            {"name": "C", "value": "200"},  # outlier
            {"name": "D", "value": "7"},
            {"name": "E", "value": "4"},
            {"name": "F", "value": "8"},
            {"name": "G", "value": "9"},
            {"name": "H", "value": "10"},
        ]
        result = filter_outliers(data, "value", 2.0)
        self.assertEqual(len(result), 7)
        names = [row["name"] for row in result]
        self.assertIn("A", names)
        self.assertIn("B", names)
        self.assertIn("D", names)
        self.assertIn("E", names)
        self.assertIn("F", names)
        self.assertIn("G", names)
        self.assertIn("H", names)
        self.assertNotIn("C", names)


if __name__ == "__main__":
    unittest.main()
