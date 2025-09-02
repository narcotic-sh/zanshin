// macOS codesigns files listed in a txt file (absolute paths)

#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <thread>
#include <atomic>
#include <mutex>
#include <queue>
#include <condition_variable>
#include <cstdlib>
#include <filesystem>
#include <chrono>

namespace fs = std::filesystem;

// Thread-safe queue for file processing
class ThreadSafeQueue {
private:
    std::queue<std::string> queue;
    std::mutex mutex;
    std::condition_variable cv;
    bool done = false;

public:
    void push(const std::string& item) {
        std::unique_lock<std::mutex> lock(mutex);
        queue.push(item);
        cv.notify_one();
    }

    bool pop(std::string& item) {
        std::unique_lock<std::mutex> lock(mutex);
        cv.wait(lock, [this] { return !queue.empty() || done; });

        if (queue.empty() && done) {
            return false;
        }

        item = queue.front();
        queue.pop();
        return true;
    }

    void setDone() {
        std::unique_lock<std::mutex> lock(mutex);
        done = true;
        cv.notify_all();
    }
};

// Thread-safe counters
class ThreadSafeCounters {
private:
    std::atomic<int> successful{0};
    std::atomic<int> failed{0};
    std::atomic<int> processed{0};
    int total;
    std::mutex print_mutex;

public:
    ThreadSafeCounters(int totalFiles) : total(totalFiles) {}

    void incrementSuccess() {
        successful++;
        updateProgress();
    }

    void incrementFailed() {
        failed++;
        updateProgress();
    }

    void updateProgress() {
        int current = ++processed;
        int percentage = (current * 100) / total;

        std::unique_lock<std::mutex> lock(print_mutex);
        std::cout << "\rProgress: " << percentage << "% ("
                  << current << "/" << total << ")" << std::flush;
    }

    void printSummary() {
        std::cout << std::endl;
        std::cout << "Successfully signed: " << successful.load()
                  << "/" << total << std::endl;
        if (failed.load() > 0) {
            std::cout << "Failed: " << failed.load() << std::endl;
        }
    }

    bool allSuccessful() {
        return successful.load() == total;
    }
};

// Parse command line arguments
bool parseArguments(int argc, char* argv[], std::string& fileList,
                   std::string& entitlements, std::string& identity) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <file_list> [options]" << std::endl;
        std::cerr << "Options:" << std::endl;
        std::cerr << "  --entitlements <file>  Path to entitlements file" << std::endl;
        std::cerr << "  --identity <id>        Signing identity (default: Developer ID Application: HAMZA QAYYUM (3LF26Z4G2R))" << std::endl;
        return false;
    }

    fileList = argv[1];
    entitlements = "";
    identity = "Developer ID Application: HAMZA QAYYUM (3LF26Z4G2R)";

    for (int i = 2; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--entitlements" && i + 1 < argc) {
            entitlements = argv[++i];
        } else if (arg == "--identity" && i + 1 < argc) {
            identity = argv[++i];
        }
    }

    return true;
}

// Read file list
std::vector<std::string> readFileList(const std::string& filePath) {
    std::vector<std::string> files;
    std::ifstream inFile(filePath);

    if (!inFile.is_open()) {
        std::cerr << "Error: Cannot open file list: " << filePath << std::endl;
        return files;
    }

    std::string line;
    while (std::getline(inFile, line)) {
        if (!line.empty()) {
            files.push_back(line);
        }
    }

    return files;
}

// Sign a single file
bool signFile(const std::string& filePath, const std::string& identity,
              const std::string& entitlements) {
    // Check if file exists
    if (!fs::exists(filePath)) {
        return false;
    }

    // Build codesign command
    std::string cmd = "codesign -s '" + identity + "' -f --timestamp --options runtime";

    if (!entitlements.empty()) {
        cmd += " --entitlements '" + entitlements + "'";
    }

    cmd += " '" + filePath + "' 2>/dev/null";

    // Execute command
    int result = system(cmd.c_str());
    return (result == 0);
}

// Worker thread function
void workerThread(ThreadSafeQueue& fileQueue, ThreadSafeCounters& counters,
                 const std::string& identity, const std::string& entitlements) {
    std::string filePath;

    while (fileQueue.pop(filePath)) {
        if (signFile(filePath, identity, entitlements)) {
            counters.incrementSuccess();
        } else {
            counters.incrementFailed();
        }
    }
}

int main(int argc, char* argv[]) {
    // Parse arguments
    std::string fileList, entitlements, identity;
    if (!parseArguments(argc, argv, fileList, entitlements, identity)) {
        return 1;
    }

    // Read file list
    std::vector<std::string> files = readFileList(fileList);
    if (files.empty()) {
        std::cerr << "No files to sign" << std::endl;
        return 1;
    }

    std::cout << "Found " << files.size() << " files to sign" << std::endl;

    // Check if entitlements file exists
    if (!entitlements.empty() && !fs::exists(entitlements)) {
        std::cerr << "Error: Entitlements file not found: " << entitlements << std::endl;
        return 1;
    }

    // Determine number of threads
    unsigned int numThreads = std::thread::hardware_concurrency();
    if (numThreads == 0) numThreads = 4;

    // For codesigning, we might want to limit threads to avoid overwhelming the system
    // since codesign itself might use multiple cores
    numThreads = std::min(numThreads, 8u);

    std::cout << "Signing with " << numThreads << " threads..." << std::endl;
    std::cout << "Identity: " << identity << std::endl;
    if (!entitlements.empty()) {
        std::cout << "Entitlements: " << entitlements << std::endl;
    }

    // Start timing
    auto startTime = std::chrono::high_resolution_clock::now();

    // Create thread-safe structures
    ThreadSafeQueue fileQueue;
    ThreadSafeCounters counters(files.size());

    // Add all files to queue
    for (const auto& file : files) {
        fileQueue.push(file);
    }
    fileQueue.setDone();

    // Create and start worker threads
    std::vector<std::thread> threads;
    for (unsigned int i = 0; i < numThreads; i++) {
        threads.push_back(std::thread(workerThread,
                                     std::ref(fileQueue),
                                     std::ref(counters),
                                     identity,
                                     entitlements));
    }

    // Wait for all threads to finish
    for (auto& thread : threads) {
        thread.join();
    }

    // Calculate elapsed time
    auto endTime = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::seconds>(endTime - startTime);

    // Print summary
    counters.printSummary();
    std::cout << "Time elapsed: " << duration.count() << " seconds" << std::endl;

    return counters.allSuccessful() ? 0 : 1;
}
