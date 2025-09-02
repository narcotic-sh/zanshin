import psutil
import time
import subprocess
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

def monitor_app():
    # Start the app.py process
    process = subprocess.Popen(["python", "app.py"])
    
    # Initialize data collection
    timestamps = []
    memory_usage = []
    start_time = time.time()
    
    try:
        # Create a live-updating plot
        plt.figure(figsize=(10, 6))
        plt.ion()  # Turn on interactive mode
        
        while process.poll() is None:  # While the process is still running
            # Get the parent process
            parent = psutil.Process(process.pid)
            
            # Get memory for parent and all children
            total_memory = parent.memory_info().rss
            for child in parent.children(recursive=True):
                try:
                    total_memory += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Convert to MB
            total_memory_mb = total_memory / (1024 * 1024)
            
            # Record data
            current_time = time.time() - start_time
            timestamps.append(current_time)
            memory_usage.append(total_memory_mb)
            
            # Update the plot
            plt.clf()
            plt.plot(timestamps, memory_usage)
            plt.title('Memory Usage Over Time')
            plt.xlabel('Time (seconds)')
            plt.ylabel('Memory Usage (MB)')
            plt.grid(True)
            
            # Add current values
            plt.text(0.02, 0.95, f"Current: {total_memory_mb:.2f} MB", transform=plt.gca().transAxes)
            plt.text(0.02, 0.90, f"Max: {max(memory_usage):.2f} MB", transform=plt.gca().transAxes)
            
            plt.draw()
            plt.pause(0.1)
            
            # Wait before next sample
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Monitoring stopped by user")
    finally:
        # Save the plot and data
        plt.ioff()
        plt.figure(figsize=(12, 8))
        plt.plot(timestamps, memory_usage)
        plt.title('Memory Usage Over Time')
        plt.xlabel('Time (seconds)')
        plt.ylabel('Memory Usage (MB)')
        plt.grid(True)
        
        # Add statistics
        avg_memory = np.mean(memory_usage)
        max_memory = max(memory_usage)
        plt.axhline(y=avg_memory, color='r', linestyle='--', label=f'Avg: {avg_memory:.2f} MB')
        plt.axhline(y=max_memory, color='g', linestyle='--', label=f'Max: {max_memory:.2f} MB')
        plt.legend()
        
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plt.savefig(f'memory_usage_{timestamp}.png')
        
        # Save raw data for later analysis
        with open(f'memory_data_{timestamp}.csv', 'w') as f:
            f.write("Time(s),Memory(MB)\n")
            for t, m in zip(timestamps, memory_usage):
                f.write(f"{t:.2f},{m:.2f}\n")
        
        # Clean up
        if process.poll() is None:
            process.terminate()
            process.wait()
        
        print(f"Maximum memory usage: {max_memory:.2f} MB")
        print(f"Average memory usage: {avg_memory:.2f} MB")
        print(f"Data saved to memory_data_{timestamp}.csv")
        print(f"Plot saved to memory_usage_{timestamp}.png")

if __name__ == "__main__":
    monitor_app()