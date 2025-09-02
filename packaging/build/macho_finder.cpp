// From a start directory, recursively finds all Mach-O executables using header magic number checking

#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <cstdlib>
#include <filesystem>
#include <cstring>

namespace fs = std::filesystem;

// Mach-O magic numbers
const uint32_t MH_MAGIC = 0xfeedface;     // 32-bit little endian
const uint32_t MH_CIGAM = 0xcefaedfe;     // 32-bit big endian
const uint32_t MH_MAGIC_64 = 0xfeedfacf;  // 64-bit little endian
const uint32_t MH_CIGAM_64 = 0xcffaedfe;  // 64-bit big endian
const uint32_t FAT_MAGIC = 0xcafebabe;    // Universal binary little endian
const uint32_t FAT_CIGAM = 0xbebafeca;    // Universal binary big endian

// Parse command line arguments
void parseArguments(int argc, char* argv[], std::string& searchPath,
                   std::string& outputFile, std::vector<std::string>& ignorePaths) {
    searchPath = ".";
    outputFile = "macho_files.txt";

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if ((arg == "-o" || arg == "--output") && i + 1 < argc) {
            outputFile = argv[++i];
        } else if (arg == "--ignore" && i + 1 < argc) {
            ignorePaths.push_back(argv[++i]);
        } else if (arg[0] != '-') {
            searchPath = arg;
        }
    }
}

// Check if a file is under any of the ignored directories
bool shouldIgnore(const std::string& filePath, const std::vector<std::string>& ignorePaths) {
    for (const auto& ignorePath : ignorePaths) {
        // Check if the file path starts with the ignore path
        // Using filesystem to properly handle path comparisons
        try {
            fs::path fileP = fs::absolute(filePath);
            fs::path ignoreP = fs::absolute(ignorePath);

            // Check if fileP is under ignoreP
            auto relativePath = fs::relative(fileP, ignoreP);
            std::string relStr = relativePath.string();

            // If the relative path doesn't start with "..", it means the file is under the ignore directory
            if (!relStr.empty() && relStr.substr(0, 2) != "..") {
                return true;
            }
        } catch (const std::exception&) {
            // If there's an error computing relative path, fall back to string comparison
            if (filePath.find(ignorePath) == 0) {
                return true;
            }
        }
    }
    return false;
}

// Check if a file is a Mach-O binary by reading magic number
bool isMachoFile(const std::string& filePath) {
    std::ifstream file(filePath, std::ios::binary);
    if (!file.is_open()) {
        return false;
    }

    // Read first 4 bytes (magic number)
    uint32_t magic;
    file.read(reinterpret_cast<char*>(&magic), sizeof(magic));

    if (!file.good()) {
        return false;
    }

    // Check against known Mach-O magic numbers
    return (magic == MH_MAGIC ||
            magic == MH_CIGAM ||
            magic == MH_MAGIC_64 ||
            magic == MH_CIGAM_64 ||
            magic == FAT_MAGIC ||
            magic == FAT_CIGAM);
}

// Get all files recursively using filesystem library
std::vector<std::string> getAllFiles(const std::string& searchPath) {
    std::vector<std::string> allFiles;

    try {
        for (const auto& entry : fs::recursive_directory_iterator(searchPath,
                fs::directory_options::skip_permission_denied)) {
            if (fs::is_regular_file(entry.status())) {
                allFiles.push_back(entry.path().string());
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Error traversing directory: " << e.what() << std::endl;
    }

    return allFiles;
}

int main(int argc, char* argv[]) {
    // Parse command line arguments
    std::string searchPath, outputFile;
    std::vector<std::string> ignorePaths;
    parseArguments(argc, argv, searchPath, outputFile, ignorePaths);

    // Convert paths to absolute paths
    try {
        searchPath = fs::absolute(searchPath).string();
        for (auto& ignorePath : ignorePaths) {
            ignorePath = fs::absolute(ignorePath).string();
        }
    } catch (const std::exception& e) {
        std::cerr << "Invalid path: " << e.what() << std::endl;
        return 1;
    }

    std::cout << "Searching for Mach-O files in: " << searchPath << std::endl;

    if (!ignorePaths.empty()) {
        std::cout << "Ignoring files in:" << std::endl;
        for (const auto& path : ignorePaths) {
            std::cout << "  " << path << std::endl;
        }
    }

    // Get all files
    std::cout << "Finding all files..." << std::endl;
    std::vector<std::string> allFiles = getAllFiles(searchPath);
    std::cout << "Found " << allFiles.size() << " total files" << std::endl;

    // Check each file for Mach-O format
    std::cout << "Checking for Mach-O format..." << std::endl;
    std::vector<std::string> machoFiles;
    int ignoredCount = 0;

    int processed = 0;
    for (const auto& filePath : allFiles) {
        if (isMachoFile(filePath)) {
            // Check if this file should be ignored
            if (shouldIgnore(filePath, ignorePaths)) {
                ignoredCount++;
            } else {
                machoFiles.push_back(filePath);
            }
        }

        // Update progress
        processed++;
        if (processed % 100 == 0 || processed == allFiles.size()) {
            std::cout << "Processed " << processed << "/" << allFiles.size()
                     << " files...\r" << std::flush;
        }
    }

    std::cout << std::endl << "Analysis complete!" << std::endl;
    std::cout << "Found " << (machoFiles.size() + ignoredCount) << " Mach-O files total" << std::endl;
    if (ignoredCount > 0) {
        std::cout << "  " << machoFiles.size() << " included" << std::endl;
        std::cout << "  " << ignoredCount << " ignored" << std::endl;
    }

    // Save results to file
    std::ofstream outFile(outputFile);
    if (!outFile.is_open()) {
        std::cerr << "Failed to open output file: " << outputFile << std::endl;
        return 1;
    }

    for (const auto& file : machoFiles) {
        outFile << file << std::endl;
    }
    outFile.close();

    std::cout << "List saved to " << outputFile << std::endl;

    // Print sample of files
    if (!machoFiles.empty()) {
        std::cout << std::endl << "Sample of found files:" << std::endl;
        int sampleSize = std::min(5, static_cast<int>(machoFiles.size()));

        for (int i = 0; i < sampleSize; i++) {
            std::cout << "  " << machoFiles[i] << std::endl;
        }

        if (machoFiles.size() > 5) {
            std::cout << "  ... and " << (machoFiles.size() - 5) << " more" << std::endl;
        }
    }

    return 0;
}