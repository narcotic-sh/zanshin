#!/usr/bin/env python3
"""
Convert PNG to ICNS file for macOS app bundles with proper padding.
Requires: Pillow (pip install Pillow)
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from PIL import Image

def add_transparent_padding(img, target_size):
    """
    Add transparent padding around an image to achieve macOS icon style.
    
    The content area is (1 - 2 * 0.09765625) = 0.8046875 of the total size.
    For a 1024x1024 icon, this means 100px padding on each side.
    
    Args:
        img: PIL Image object
        target_size: Target size (width and height) for the square output
    
    Returns:
        New PIL Image with transparent padding
    """
    # Calculate padding (0.09765625 of the total size on each side)
    padding_ratio = 0.09765625
    padding = int(target_size * padding_ratio)
    
    # Calculate the size the content should be
    content_size = target_size - (2 * padding)
    
    # Create a new transparent image at target size
    padded_img = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
    
    # Resize the original image to fit in the content area
    # Maintain aspect ratio
    img_width, img_height = img.size
    aspect_ratio = img_width / img_height
    
    if aspect_ratio > 1:
        # Wider than tall
        new_width = content_size
        new_height = int(content_size / aspect_ratio)
    else:
        # Taller than wide or square
        new_height = content_size
        new_width = int(content_size * aspect_ratio)
    
    # Resize the image
    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Calculate position to center the image in the content area
    x_offset = padding + (content_size - new_width) // 2
    y_offset = padding + (content_size - new_height) // 2
    
    # Paste the resized image onto the transparent background
    padded_img.paste(resized, (x_offset, y_offset), resized)
    
    return padded_img

def create_icns(png_path, output_path=None, add_padding=True):
    """
    Convert a PNG file to ICNS format with all required sizes.
    
    Args:
        png_path: Path to the input PNG file
        output_path: Optional output path for ICNS file (defaults to same name as input)
        add_padding: Whether to add transparent padding (default: True)
    
    Returns:
        Path to the created ICNS file
    """
    # Validate input
    png_path = Path(png_path)
    if not png_path.exists():
        raise FileNotFoundError(f"Input file not found: {png_path}")
    
    if not png_path.suffix.lower() == '.png':
        raise ValueError(f"Input file must be a PNG: {png_path}")
    
    # Set output path if not specified
    if output_path is None:
        output_path = png_path.with_suffix('.icns')
    else:
        output_path = Path(output_path)
    
    # Define required icon sizes for macOS
    # Format: (size, scale, filename)
    icon_sizes = [
        (16, 1, 'icon_16x16.png'),
        (16, 2, 'icon_16x16@2x.png'),
        (32, 1, 'icon_32x32.png'),
        (32, 2, 'icon_32x32@2x.png'),
        (128, 1, 'icon_128x128.png'),
        (128, 2, 'icon_128x128@2x.png'),
        (256, 1, 'icon_256x256.png'),
        (256, 2, 'icon_256x256@2x.png'),
        (512, 1, 'icon_512x512.png'),
        (512, 2, 'icon_512x512@2x.png'),
    ]
    
    # Create temporary directory for icon files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        iconset_path = temp_path / 'icon.iconset'
        iconset_path.mkdir()
        
        # Open the original image
        print(f"Loading image: {png_path}")
        with Image.open(png_path) as img:
            # Convert to RGBA if necessary
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Get original dimensions
            orig_width, orig_height = img.size
            print(f"Original size: {orig_width}x{orig_height}")
            
            if add_padding:
                print("Adding macOS-style transparent padding (9.765625% on each side)")
            
            # Generate all required sizes
            for base_size, scale, filename in icon_sizes:
                actual_size = base_size * scale
                
                if add_padding:
                    # Create image with padding
                    icon_img = add_transparent_padding(img, actual_size)
                else:
                    # Simple resize without padding
                    icon_img = img.resize((actual_size, actual_size), Image.Resampling.LANCZOS)
                
                # Save to iconset directory
                output_file = iconset_path / filename
                icon_img.save(output_file, 'PNG')
                
                # Calculate actual content size for display
                if add_padding:
                    padding = int(actual_size * 0.09765625)
                    content_size = actual_size - (2 * padding)
                    print(f"Created: {filename} ({actual_size}x{actual_size}, content: {content_size}x{content_size})")
                else:
                    print(f"Created: {filename} ({actual_size}x{actual_size})")
        
        # Use iconutil to create the ICNS file
        print(f"\nCreating ICNS file: {output_path}")
        result = os.system(f'iconutil -c icns "{iconset_path}" -o "{output_path}"')
        
        if result != 0:
            # Fallback: try using sips if iconutil fails
            print("iconutil failed, trying sips as fallback...")
            
            # Create ICNS using sips (alternative method)
            largest_png = None
            for file in iconset_path.glob('*.png'):
                largest_png = file
                break
            
            if largest_png:
                result = os.system(f'sips -s format icns "{largest_png}" --out "{output_path}"')
                if result != 0:
                    raise RuntimeError("Failed to create ICNS file. Make sure you're running on macOS.")
            else:
                raise RuntimeError("No PNG files were created in the iconset.")
    
    print(f"✅ Successfully created: {output_path}")
    return output_path

def main():
    """Main entry point for command-line usage."""
    if len(sys.argv) < 2:
        print("Usage: python create_icns.py <input.png> [output.icns] [--no-padding]")
        print("\nExample:")
        print("  python create_icns.py app_icon.png")
        print("  python create_icns.py app_icon.png custom_name.icns")
        print("  python create_icns.py app_icon.png --no-padding")
        print("\nBy default, adds macOS-style transparent padding (9.765625% on each side).")
        print("Use --no-padding to disable this behavior.")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = None
    add_padding = True
    
    # Parse optional arguments
    args = sys.argv[2:]
    for arg in args:
        if arg == '--no-padding':
            add_padding = False
        elif not arg.startswith('--'):
            output_path = arg
    
    try:
        create_icns(input_path, output_path, add_padding)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()