#!/usr/bin/env python3
"""
Format pip-licenses output into columns with configurable spacing.
"""

import sys
import math
import argparse
import subprocess


def get_packages():
    """Get package names from pip-licenses."""
    try:
        # Run pip-licenses command
        result = subprocess.run(
            ['pip-licenses', '--format=plain', '--no-version'],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse output - skip first line
        lines = result.stdout.strip().split('\n')[1:]
        packages = []
        for line in lines:
            if line.strip():
                # Get first column (package name)
                package = line.split()[0]
                packages.append(package)

        return sorted(packages)

    except subprocess.CalledProcessError as e:
        print(f"Error running pip-licenses: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("pip-licenses not found. Please install it with: pip install pip-licenses", file=sys.stderr)
        sys.exit(1)


def format_columns(packages, num_cols=3, spacing=4):
    """Format packages into columns with specified spacing."""
    if not packages:
        return

    num_packages = len(packages)
    rows_per_col = math.ceil(num_packages / num_cols)

    # Find the max width for each column
    col_widths = []
    for col in range(num_cols):
        max_width = 0
        for row in range(rows_per_col):
            idx = col * rows_per_col + row
            if idx < num_packages:
                max_width = max(max_width, len(packages[idx]))
        col_widths.append(max_width)

    # Print with proper spacing
    for row in range(rows_per_col):
        line_parts = []
        for col in range(num_cols):
            idx = col * rows_per_col + row
            if idx < num_packages:
                if col < num_cols - 1:  # Not the last column
                    line_parts.append(f'{packages[idx]:<{col_widths[col]}}' + ' ' * spacing)
                else:  # Last column doesn't need trailing spaces
                    line_parts.append(packages[idx])
        print(''.join(line_parts).rstrip())


def main():
    parser = argparse.ArgumentParser(
        description='Format pip-licenses output into columns with configurable spacing.'
    )
    parser.add_argument(
        '--spaces',
        type=int,
        default=4,
        help='Number of spaces between columns (default: 4)'
    )
    parser.add_argument(
        '--columns',
        type=int,
        default=3,
        help='Number of columns (default: 3)'
    )

    args = parser.parse_args()

    if args.spaces < 0:
        print("Error: --spaces must be non-negative", file=sys.stderr)
        sys.exit(1)

    if args.columns < 1:
        print("Error: --columns must be at least 1", file=sys.stderr)
        sys.exit(1)

    packages = get_packages()
    format_columns(packages, num_cols=args.columns, spacing=args.spaces)


if __name__ == '__main__':
    main()
