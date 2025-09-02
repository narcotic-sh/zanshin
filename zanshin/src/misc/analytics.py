import sqlite3
import matplotlib.pyplot as plt
import os
import numpy as np

def generate_diarization_time_graph(db_path=config.DB_PATH, output_path="diarization_analysis.png"):
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query for successful jobs with both duration and diarization_time
    cursor.execute('''
    SELECT duration, diarization_time
    FROM media
    WHERE status = 'success'
      AND duration IS NOT NULL
      AND diarization_time IS NOT NULL
    ''')

    results = cursor.fetchall()
    conn.close()

    if not results:
        print("No successful jobs with duration and diarization time found.")
        return False

    # Extract data for plotting
    durations = [row[0] for row in results]
    diarization_times = [row[1] for row in results]

    # Create the scatterplot
    plt.figure(figsize=(10, 6))
    plt.scatter(durations, diarization_times, alpha=0.7)

    # Add trendline and equation
    if len(results) > 1:
        # Calculate the line equation (y = mx + b)
        z = np.polyfit(durations, diarization_times, 1)
        slope, intercept = z
        p = np.poly1d(z)

        # Add trendline to plot
        plt.plot(durations, p(durations), "r--", alpha=0.8)

        # Calculate correlation coefficient
        correlation = np.corrcoef(durations, diarization_times)[0, 1]

        # Add line equation and correlation to the plot
        equation_text = f"y = {slope:.4f}x + {intercept:.4f}"
        plt.figtext(0.15, 0.85,
                   f"Line equation: {equation_text}\nCorrelation: {correlation:.2f}",
                   fontsize=10,
                   bbox=dict(facecolor='white', alpha=0.8))

    # Add labels and title
    plt.xlabel('Media Duration (seconds)')
    plt.ylabel('Diarization Time (seconds)')
    plt.title('Diarization Processing Time vs. Media Duration')
    plt.grid(True, linestyle='--', alpha=0.7)

    # Save the plot
    plt.tight_layout()
    plt.savefig(output_path)
    print(f"Scatterplot saved to {output_path}")

    # Show the plot
    plt.show()
    return True

if __name__ == "__main__":
    generate_diarization_time_graph()
