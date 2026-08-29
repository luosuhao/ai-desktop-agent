"""
Data Processor - A sample Python script for testing Coding Agent.

This script reads a CSV file, processes the data, and generates a report.
There are several issues that need to be fixed:

1. The calculate_average function has a bug when the list is empty
2. The save_report function doesn't create the output directory
3. TODO: Add a function to filter out outliers
"""

import csv
import os


def load_data(filepath):
    """Load CSV data and return as list of dicts."""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    total = sum(numbers)
    return total / len(numbers)  # BUG: crashes when numbers is empty


def calculate_stats(data, column):
    """Calculate min, max, avg for a given column."""
    values = []
    for row in data:
        try:
            values.append(float(row[column]))
        except (ValueError, KeyError):
            continue

    if not values:
        return None

    return {
        "min": min(values),
        "max": max(values),
        "avg": calculate_average(values),
        "count": len(values)
    }


def save_report(stats, output_path):
    """Save statistics report to a file."""
    with open(output_path, 'w') as f:  # BUG: doesn't create directory if missing
        f.write("Data Analysis Report\n")
        f.write("====================\n\n")
        for column, stat in stats.items():
            if stat:
                f.write(f"{column}:\n")
                f.write(f"  Min: {stat['min']}\n")
                f.write(f"  Max: {stat['max']}\n")
                f.write(f"  Avg: {stat['avg']}\n")
                f.write(f"  Count: {stat['count']}\n\n")


# TODO: Add a function filter_outliers(data, column, threshold)
# that filters out rows where the value in column is more than
# threshold standard deviations from the mean.


def main():
    # Test data
    data = [
        {"name": "Alice", "score": "85"},
        {"name": "Bob", "score": "92"},
        {"name": "Charlie", "score": "78"},
        {"name": "Diana", "score": "95"},
    ]

    stats = {
        "score": calculate_stats(data, "score")
    }
    print(f"Stats: {stats}")

    # Test empty list bug
    # print(calculate_average([]))  # Uncomment to see the crash

    # Test save_report
    # save_report(stats, "./outputs/report.txt")


if __name__ == "__main__":
    main()
