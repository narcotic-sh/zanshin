#!/usr/bin/env python3

import sqlite3
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from itertools import combinations
import sys
import os
import colour
from colour.models import RGB_COLOURSPACE_sRGB
from colour import CCS_ILLUMINANTS

# Constants from your original code
GOLDEN_ANGLE = 137.508  # Degrees
L_MIN = 0.325           # Minimum lightness
L_MAX = 0.85            # Maximum lightness
FIXED_CHROMA = 0.15     # Fixed chroma value
W = 0.5                 # Weight for balancing segment count and speaking time
L_a = 63.66             # Adapting luminance for H-K effect

# You'll need to ensure this matches your environment
RGB_COLOURSPACE_sRGB = colour.RGB_COLOURSPACES['sRGB']
D65 = CCS_ILLUMINANTS['CIE 1931 2 Degree Standard Observer']['D65']

def oklch_to_hex(L, C, H):
    """Convert OKLCH color to hex code."""
    JCh = np.array([L, C, H])
    Jab = colour.models.JCh_to_Jab(JCh)
    XYZ = colour.models.oklab.Oklab_to_XYZ(Jab)
    RGB = colour.XYZ_to_RGB(XYZ, RGB_COLOURSPACE_sRGB, illuminant=D65, apply_cctf_encoding=True)
    RGB = np.clip(RGB, 0, 1)  # Ensure RGB values are within [0, 1]
    return colour.notation.RGB_to_HEX(RGB)

def compute_hk_factor(L, C, H):
    """Compute the Helmholtz-Kohlrausch factor Γ for the given OKLCH color."""
    # Convert OKLCH to XYZ
    JCh = np.array([L, C, H])
    Jab = colour.models.JCh_to_Jab(JCh)
    XYZ = colour.models.oklab.Oklab_to_XYZ(Jab)

    # Compute CIE uv chromaticity for the color
    denominator = XYZ[0] + 15 * XYZ[1] + 3 * XYZ[2]
    if denominator == 0:
        uv = np.array([0.0, 0.0])
    else:
        uv = np.array([4 * XYZ[0] / denominator, 9 * XYZ[1] / denominator])

    # Reference white: D65
    D65_XYZ = np.array([95.047, 100.0, 108.883]) / 100  # Normalize to [0, 1]
    denominator_w = D65_XYZ[0] + 15 * D65_XYZ[1] + 3 * D65_XYZ[2]
    uv_c = np.array([4 * D65_XYZ[0] / denominator_w, 9 * D65_XYZ[1] / denominator_w])

    # Compute Γ using Nayatani's method
    Gamma = colour.HelmholtzKohlrausch_effect_object_Nayatani1997(
        uv, uv_c, L_a, method='VCC'
    )
    return Gamma

def hex_to_oklch(hex_color):
    """Convert hex color back to OKLCH."""
    # Convert hex to RGB
    RGB = colour.notation.HEX_to_RGB(hex_color)

    # Convert RGB to XYZ
    XYZ = colour.RGB_to_XYZ(RGB, RGB_COLOURSPACE_sRGB, illuminant=D65, apply_cctf_decoding=True)

    # Convert XYZ to Oklab
    Jab = colour.models.oklab.XYZ_to_Oklab(XYZ)

    # Convert Oklab (Jab) to OKLCH (JCh)
    JCh = colour.models.Jab_to_JCh(Jab)

    return JCh  # Returns [L, C, H]

def calculate_oklch_distance(color1_oklch, color2_oklch):
    """Calculate Euclidean distance between two OKLCH colors."""
    # Convert OKLCH to OKLAB for Euclidean distance
    L1, C1, H1 = color1_oklch
    L2, C2, H2 = color2_oklch

    # Convert to radians for trigonometric functions
    H1_rad = np.deg2rad(H1)
    H2_rad = np.deg2rad(H2)

    # Convert to OKLAB coordinates
    a1 = C1 * np.cos(H1_rad)
    b1 = C1 * np.sin(H1_rad)

    a2 = C2 * np.cos(H2_rad)
    b2 = C2 * np.sin(H2_rad)

    # Calculate Euclidean distance
    distance = np.sqrt((L1 - L2)**2 + (a1 - a2)**2 + (b1 - b2)**2)

    return distance

def generate_speaker_colors(merged_segments):
    """Generate speaker colors from segments data."""
    # Calculate total speaking time and segment counts per speaker
    speaking_times = {}
    segment_counts = {}
    for segment in merged_segments:
        duration = segment['end'] - segment['start']
        speaker = segment['speaker']
        speaking_times[speaker] = speaking_times.get(speaker, 0) + duration
        segment_counts[speaker] = segment_counts.get(speaker, 0) + 1

    # Calculate total speaking time and segments across all speakers
    total_speaking_time = sum(speaking_times.values())
    total_segments = sum(segment_counts.values())

    # Rationalize speaking times and segment counts
    r_speaking_times = {speaker: time / total_speaking_time if total_speaking_time > 0 else 0
                        for speaker, time in speaking_times.items()}
    r_segment_counts = {speaker: count / total_segments if total_segments > 0 else 0
                        for speaker, count in segment_counts.items()}

    # Calculate lightness scores
    lightness_scores = {}
    for speaker in speaking_times:
        num_segments = r_segment_counts.get(speaker, 0)
        speaking_time = r_speaking_times.get(speaker, 0)
        score = W * num_segments + (1 - W) * (1 - speaking_time)
        lightness_scores[speaker] = score

    # Normalize lightness scores to [L_MIN, L_MAX]
    scores = list(lightness_scores.values())
    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0
    lightness = {}
    power = 0.33  # Adjust this value to control compression
    for speaker, score in lightness_scores.items():
        if max_score == min_score:
            normalized = 0.5
        else:
            normalized = ((score - min_score) / (max_score - min_score)) ** power
        lightness[speaker] = L_MIN + normalized * (L_MAX - L_MIN)

    # Sort speakers by speaking time (descending)
    speakers = sorted(speaking_times, key=speaking_times.get, reverse=True)

    # Assign colors and build speaker color map with H-K adjustment
    speaker_color_map = {}
    for i, speaker in enumerate(speakers):
        L_original = lightness[speaker]
        H = ((i+2) * GOLDEN_ANGLE) % 360
        C = FIXED_CHROMA

        # Compute Γ for the original OKLCH color
        Gamma = compute_hk_factor(L_original, C, H)

        # Adjust lightness
        L_adjusted = L_original / Gamma
        L_adjusted = max(0.0, min(1.0, L_adjusted))  # Clamp to [0, 1]

        # Convert adjusted OKLCH to hex
        hex_color = oklch_to_hex(L_adjusted, C, H)
        speaker_color_map[speaker] = hex_color

    return speaker_color_map

def visualize_color_distances(speaker_color_map, media_id):
    """Create visualization of color distances and save as PNG."""
    # Calculate distances between all color pairs
    speakers_list = list(speaker_color_map.keys())
    color_pairs = list(combinations(speakers_list, 2))

    # Create a figure to display color pairs and distances
    n_pairs = len(color_pairs)
    fig, axes = plt.subplots(n_pairs, 1, figsize=(10, 2 * n_pairs))

    if n_pairs == 1:
        axes = [axes]  # Make it iterable for single pair case

    for idx, (speaker1, speaker2) in enumerate(color_pairs):
        color1_hex = speaker_color_map[speaker1]
        color2_hex = speaker_color_map[speaker2]

        # Convert hex colors back to OKLCH
        color1_oklch = hex_to_oklch(color1_hex)
        color2_oklch = hex_to_oklch(color2_hex)

        # Calculate Euclidean distance
        distance = calculate_oklch_distance(color1_oklch, color2_oklch)

        # Create color patches
        ax = axes[idx]
        ax.set_xlim(0, 3)
        ax.set_ylim(0, 1)

        # Draw color patches
        patch1 = mpatches.Rectangle((0.5, 0.25), 0.5, 0.5, facecolor=color1_hex)
        patch2 = mpatches.Rectangle((2.0, 0.25), 0.5, 0.5, facecolor=color2_hex)

        ax.add_patch(patch1)
        ax.add_patch(patch2)

        # Add text labels
        ax.text(0.5, 0.8, f"{speaker1}", ha='left', va='center')
        ax.text(2.0, 0.8, f"{speaker2}", ha='left', va='center')
        ax.text(1.5, 0.5, f"Distance: {distance:.4f}", ha='center', va='center',
                fontsize=12, bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

        # Remove axis ticks and labels
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect('equal')

        # Add a separator line
        if idx < n_pairs - 1:
            ax.axhline(y=0, color='gray', linewidth=0.5)

    plt.tight_layout()
    plt.suptitle(f'Color Pair Distances (OKLCH) - ID: {media_id}', fontsize=16, y=1.02)

    # Save the plot as PNG
    filename = f"{media_id}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Saved visualization to {filename}")

    # Show the plot
    plt.show()
    plt.close()

def main():
    """Main function to run the color distance visualization in a loop."""
    while True:
        print("\n" + "="*50)
        media_id = input("Enter media ID (or 'q' to quit): ")

        if media_id.lower() == 'q':
            print("Exiting...")
            break

        # Connect to database
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()

        # Fetch merged_segments for the given ID
        cursor.execute("SELECT merged_segments FROM media WHERE id = ?", (media_id,))
        result = cursor.fetchone()

        if not result or result[0] is None:
            print(f"No segments data found for ID: {media_id}")
            conn.close()
            continue

        merged_segments = json.loads(result[0])
        conn.close()

        # Generate speaker colors
        speaker_color_map = generate_speaker_colors(merged_segments)

        # Visualize color distances and save as PNG
        visualize_color_distances(speaker_color_map, media_id)

        print(f"Completed processing for ID: {media_id}")

if __name__ == "__main__":
    main()
