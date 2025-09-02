#!/usr/bin/env python3
"""
Script to list image resolutions in an ICNS file.
"""

import sys
import struct
from pathlib import Path

def read_icns_resolutions(icns_path):
    """
    Read an ICNS file and extract the resolutions of all images within it.
    
    Args:
        icns_path (str): Path to the ICNS file
        
    Returns:
        list: List of tuples containing (type_code, width, height, bit_depth)
    """
    
    # Common ICNS type codes and their resolutions
    icns_types = {
        b'ICON': (32, 32, 1),
        b'ICN#': (32, 32, 1),
        b'icm#': (16, 12, 1),
        b'icm4': (16, 12, 4),
        b'icm8': (16, 12, 8),
        b'ics#': (16, 16, 1),
        b'ics4': (16, 16, 4),
        b'ics8': (16, 16, 8),
        b'is32': (16, 16, 24),
        b's8mk': (16, 16, 8),
        b'icl4': (32, 32, 4),
        b'icl8': (32, 32, 8),
        b'il32': (32, 32, 24),
        b'l8mk': (32, 32, 8),
        b'ich#': (48, 48, 1),
        b'ich4': (48, 48, 4),
        b'ich8': (48, 48, 8),
        b'ih32': (48, 48, 24),
        b'h8mk': (48, 48, 8),
        b'it32': (128, 128, 24),
        b't8mk': (128, 128, 8),
        b'icp4': (16, 16, 32),
        b'icp5': (32, 32, 32),
        b'icp6': (64, 64, 32),
        b'ic07': (128, 128, 32),
        b'ic08': (256, 256, 32),
        b'ic09': (512, 512, 32),
        b'ic10': (1024, 1024, 32),
        b'ic11': (32, 32, 32),
        b'ic12': (64, 64, 32),
        b'ic13': (256, 256, 32),
        b'ic14': (512, 512, 32),
    }
    
    resolutions = []
    
    try:
        with open(icns_path, 'rb') as f:
            # Read ICNS header
            header = f.read(8)
            if header[:4] != b'icns':
                raise ValueError("Not a valid ICNS file")
            
            file_size = struct.unpack('>I', header[4:8])[0]
            
            # Read through all the icon entries
            while f.tell() < file_size:
                entry_header = f.read(8)
                if len(entry_header) < 8:
                    break
                
                type_code = entry_header[:4]
                entry_size = struct.unpack('>I', entry_header[4:8])[0]
                
                if type_code in icns_types:
                    width, height, bit_depth = icns_types[type_code]
                    resolutions.append((type_code.decode('ascii'), width, height, bit_depth))
                
                # Skip to next entry
                f.seek(f.tell() + entry_size - 8)
    
    except FileNotFoundError:
        print(f"Error: File '{icns_path}' not found.")
        return []
    except Exception as e:
        print(f"Error reading ICNS file: {e}")
        return []
    
    return resolutions

def main():
    if len(sys.argv) != 2:
        print("Usage: python icns_resolutions.py <path_to_icns_file>")
        sys.exit(1)
    
    icns_file = sys.argv[1]
    
    if not Path(icns_file).exists():
        print(f"Error: File '{icns_file}' does not exist.")
        sys.exit(1)
    
    print(f"Analyzing ICNS file: {icns_file}")
    print("-" * 50)
    
    resolutions = read_icns_resolutions(icns_file)
    
    if not resolutions:
        print("No valid icon entries found in the file.")
        return
    
    print(f"Found {len(resolutions)} icon entries:")
    print()
    print("Type Code | Width x Height | Bit Depth")
    print("-" * 40)
    
    for type_code, width, height, bit_depth in resolutions:
        print(f"{type_code:>8} | {width:>4} x {height:<6} | {bit_depth:>2} bit")
    
    # Summary of unique resolutions
    unique_resolutions = list(set((width, height) for _, width, height, _ in resolutions))
    unique_resolutions.sort(key=lambda x: x[0] * x[1])  # Sort by total pixels
    
    print("\nUnique resolutions found:")
    for width, height in unique_resolutions:
        print(f"  {width} x {height}")

if __name__ == "__main__":
    main()
