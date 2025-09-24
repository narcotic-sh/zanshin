from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import subprocess
import shutil
import sys
import json
import tempfile
import plistlib
from pathlib import Path

def delete_path(path):
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
    except Exception as e:
        print(f"Error deleting {path}: {e}")

def get_ffmpeg_download_links(url="https://www.osxexperts.net/"):
    """
    Fetches download links for ffmpeg and ffprobe Apple Silicon binaries.

    Returns:
        dict: Dictionary with 'ffmpeg' and 'ffprobe' keys containing download URLs
    """
    try:
        # Fetch the HTML content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all buttons, links, and other clickable elements
        clickable_elements = soup.find_all(['button', 'a', 'input', 'div'],
                                         attrs={'onclick': True}) + soup.find_all('a', href=True)

        results = {}

        for element in clickable_elements:
            # Get the text content of the element
            text = element.get_text(strip=True).lower()

            # Check for ffmpeg + apple silicon
            if 'ffmpeg' in text and 'apple silicon' in text:
                # Try to get the download link
                link = None
                if element.name == 'a' and element.get('href'):
                    link = urljoin(url, element['href'])
                elif element.get('onclick'):
                    # Extract URL from onclick if present
                    onclick = element['onclick']
                    url_match = re.search(r'["\']([^"\']*(?:\.zip|\.tar\.gz|\.dmg|\.pkg)[^"\']*)["\']', onclick)
                    if url_match:
                        link = urljoin(url, url_match.group(1))

                if link:
                    results['ffmpeg'] = link

            # Check for ffprobe + apple silicon
            elif 'ffprobe' in text and 'apple silicon' in text:
                # Try to get the download link
                link = None
                if element.name == 'a' and element.get('href'):
                    link = urljoin(url, element['href'])
                elif element.get('onclick'):
                    # Extract URL from onclick if present
                    onclick = element['onclick']
                    url_match = re.search(r'["\']([^"\']*(?:\.zip|\.tar\.gz|\.dmg|\.pkg)[^"\']*)["\']', onclick)
                    if url_match:
                        link = urljoin(url, url_match.group(1))

                if link:
                    results['ffprobe'] = link

        return results

    except requests.RequestException as e:
        print(f"Error fetching the page: {e}")
        return {}
    except Exception as e:
        print(f"Error parsing the page: {e}")
        return {}

def download_file(url, directory, filename=None):
    Path(directory).mkdir(parents=True, exist_ok=True)
    if filename is None:
        filename = url.split('/')[-1]
    response = requests.get(url)
    file_path = Path(directory) / filename
    with open(file_path, 'wb') as f:
        f.write(response.content)
    return file_path.as_posix()

def get_and_install_github_release(api_url, asset_name, cwd=None, tool_name="tool", flatten_extracted_dir=False):
    """
    Download and install a tool from GitHub releases.

    Args:
        api_url: GitHub API URL for the latest release (e.g., "https://api.github.com/repos/owner/repo/releases/latest")
        asset_name: Name of the asset file to download (e.g., "uv-aarch64-apple-darwin.tar.gz")
        cwd: Directory where the tool will be installed
        tool_name: Name of the tool for logging purposes
        flatten_extracted_dir: If True and a subdirectory is extracted, move its contents up one level

    Returns:
        Path object of the installation directory
    """
    cwd_path = Path(cwd)

    # Fetch the latest release information from the GitHub API
    response = requests.get(api_url)
    response.raise_for_status()

    # Parse the JSON response
    release_data = response.json()

    # Find the specified asset
    download_url = None
    for asset in release_data.get("assets", []):
        if asset.get("name") == asset_name:
            download_url = asset.get("browser_download_url")
            break

    if not download_url:
        exit_on_error(f"Could not find {asset_name} in the latest release")

    # Get the version for better naming
    version = release_data.get("tag_name", "latest")
    print(f"Found {tool_name} version {version}")

    # Determine file extension and download path
    file_ext = '.tar.gz' if asset_name.endswith('.tar.gz') else ('.' + asset_name.split('.')[-1])

    download_path = cwd_path / f"{tool_name}-{version}{file_ext}"
    print(f"Downloading to {download_path}...")

    with requests.get(download_url, stream=True) as r:
        r.raise_for_status()
        with open(download_path, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    # Extract based on file type
    if file_ext == '.tar.gz':
        # Extract tarball
        subprocess.run(
            ["tar", "-xf", str(download_path)],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
    elif file_ext == '.zip':
        # Extract zip file
        subprocess.run(
            ["unzip", "-q", str(download_path), "-d", str(cwd_path)],
            check=True,
            capture_output=True,
            text=True
        )
    else:
        exit_on_error(f"Unsupported archive format: {file_ext}")

    # If flatten_extracted_dir is True, move contents from extracted subdirectory
    if flatten_extracted_dir:
        # Expected directory name is the asset name without the extension
        extracted_dir_name = asset_name.replace(file_ext, '')
        extracted_dir = cwd_path / extracted_dir_name

        if extracted_dir.exists():
            # Move all contents from the extracted directory to cwd
            for item in os.listdir(extracted_dir):
                source = extracted_dir / item
                destination = cwd_path / item

                # Handle file overwrite
                if destination.exists():
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    else:
                        os.remove(destination)

                # Move the file/directory
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)

            # Remove the extracted directory
            shutil.rmtree(extracted_dir)

    # Make all executables in the directory executable
    for file_path in cwd_path.iterdir():
        if file_path.is_file():
            # Check if file might be an executable (no extension or common executable names)
            file_name = file_path.name
            if not '.' in file_name or file_name in ['uv', 'uvx', 'deno']:
                try:
                    os.chmod(file_path, 0o755)
                except:
                    pass  # Ignore permission errors

    # Remove the downloaded archive
    os.remove(download_path)

    print(f"Successfully installed {tool_name} {version}")

    return cwd_path

def exit_on_error(message):
    print(f"Error: {message}")
    sys.exit(1)

def build_pkg(BUILD_PATH, TARBALL_PATH, version, notarize=False):

    # Define paths and filenames
    APP_DIR = os.path.join(BUILD_PATH, "Zanshin.app")
    CONTENTS_DIR = os.path.join(APP_DIR, "Contents")
    MACOS_DIR = os.path.join(CONTENTS_DIR, "MacOS")
    RESOURCES_DIR = os.path.join(CONTENTS_DIR, "Resources")
    PKG_ROOT = os.path.join(BUILD_PATH, "pkgroot")
    SCRIPTS_DIR = os.path.join(BUILD_PATH, "scripts")
    OUTPUT_PKG = os.path.join(BUILD_PATH, f"../dist/Zanshin_{version}.pkg")
    TEMP_TARBALL_DIR = os.path.join(PKG_ROOT, "private", "var", "tmp", "Zanshin")
    ENTITLEMENTS_FILE = os.path.join(BUILD_PATH, "Zanshin.entitlements")  # Entitlements file path

    # File paths
    INFO_PLIST_FILE = os.path.join(BUILD_PATH, "Info.plist")
    ZANSHIN_EXECUTABLE_FILE = os.path.join(BUILD_PATH, "Zanshin")
    PREINSTALL_SCRIPT_FILE = os.path.join(BUILD_PATH, "preinstall")
    POSTINSTALL_SCRIPT_FILE = os.path.join(BUILD_PATH, "postinstall")
    ICNS_FILE = os.path.join(BUILD_PATH, "../assets/Zanshin.icns")

    # Validate tar.xz file
    if not os.path.isfile(TARBALL_PATH):
        exit_on_error(f"File {TARBALL_PATH} does not exist.")
    if not TARBALL_PATH.endswith('.tar.xz'):
        exit_on_error(f"File {TARBALL_PATH} is not a .tar.xz file.")

    # Validate template files exist
    for file in [INFO_PLIST_FILE, ZANSHIN_EXECUTABLE_FILE, POSTINSTALL_SCRIPT_FILE, ENTITLEMENTS_FILE]:
        if not os.path.isfile(file):
            exit_on_error(f"Template file {file} does not exist. Please create it first.")

    # Clean up any existing files
    for path in [APP_DIR, PKG_ROOT, SCRIPTS_DIR, OUTPUT_PKG]:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    # Step 1: Create .app bundle
    print("Creating Zanshin.app bundle...")
    os.makedirs(MACOS_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)  # Add this line

    # Copy Info.plist to Contents directory
    shutil.copy(INFO_PLIST_FILE, os.path.join(CONTENTS_DIR, "Info.plist"))

    # Copy icon file to Resources directory
    if os.path.exists(ICNS_FILE):
        shutil.copy(ICNS_FILE, os.path.join(RESOURCES_DIR, "icon.icns"))
    else:
        print("Warning: Zanshin.icns not found. App will have no icon.")

    # Copy Zanshin executable to MacOS directory
    shutil.copy(ZANSHIN_EXECUTABLE_FILE, os.path.join(MACOS_DIR, "Zanshin"))
    os.chmod(os.path.join(MACOS_DIR, "Zanshin"), 0o755)  # Make executable

    # Step 2: Code sign the app bundle
    print("Code signing Zanshin.app...")
    try:
        subprocess.run([
            "codesign",
            "-s", "Developer ID Application: HAMZA QAYYUM (3LF26Z4G2R)",
            "-f", "--timestamp",
            "--options", "runtime",
            "--entitlements", ENTITLEMENTS_FILE,
            APP_DIR
        ], check=True)
    except subprocess.CalledProcessError:
        exit_on_error("Failed to code sign the application.")

    # Step 3: Set up postinstall script
    print("Setting up postinstall script...")
    os.makedirs(SCRIPTS_DIR, exist_ok=True)

    # Copy preinstall script
    shutil.copy(PREINSTALL_SCRIPT_FILE, os.path.join(SCRIPTS_DIR, "preinstall"))
    os.chmod(os.path.join(SCRIPTS_DIR, "preinstall"), 0o755)

    # Copy postinstall script
    shutil.copy(POSTINSTALL_SCRIPT_FILE, os.path.join(SCRIPTS_DIR, "postinstall"))
    os.chmod(os.path.join(SCRIPTS_DIR, "postinstall"), 0o755)  # Make executable

    # Step 4: Prepare package root
    print("Preparing package root...")
    os.makedirs(os.path.join(PKG_ROOT, "Applications"), exist_ok=True)
    os.makedirs(TEMP_TARBALL_DIR, exist_ok=True)

    # Move .app and copy tar.xz to temporary location
    subprocess.run(["ditto", APP_DIR, os.path.join(PKG_ROOT, "Applications", "Zanshin.app")], check=True)
    shutil.rmtree(APP_DIR)
    shutil.copy(TARBALL_PATH, os.path.join(TEMP_TARBALL_DIR, "tarball.tar.xz"))

    # Step 5: Build and sign .pkg with scripts in one step
    print(f"Building and signing {OUTPUT_PKG}...")
    subprocess.run([
        "pkgbuild",
        "--root", PKG_ROOT,
        "--scripts", SCRIPTS_DIR,
        "--install-location", "/",
        "--identifier", "com.Narcotic.Zanshin",
        "--version", version,
        "--sign", "Developer ID Installer: HAMZA QAYYUM (3LF26Z4G2R)",
        "--timestamp",
        OUTPUT_PKG
    ], check=True)

    # Copy .app bundle to current directory using ditto
    subprocess.run(["ditto", os.path.join(PKG_ROOT, "Applications/Zanshin.app"), "../dist/Zanshin.app"], cwd=BUILD_PATH, check=True)

    # Clean up
    shutil.rmtree(PKG_ROOT)
    shutil.rmtree(SCRIPTS_DIR)

    print(f"Success! Zanshin_{version}.pkg has been created and signed.")

    if notarize:
        print('Notarizing...')
        subprocess.run(["xcrun", "notarytool", "submit", OUTPUT_PKG, "--keychain-profile", "notary-profile", "--wait"], check=True)
        subprocess.run(["xcrun", "stapler", "staple", OUTPUT_PKG], check=True)
        print('Notarization complete')

def update_version_plist(plist_path, version):
    # Convert path to a Path object
    file_path = Path(plist_path)

    # Check if the file exists
    if not file_path.exists():
        print(f"Error: File not found at {plist_path}")
        return False

    # Read the plist file
    with open(file_path, 'rb') as fp:
        plist_data = plistlib.load(fp)

    # Update the version values
    plist_data['CFBundleVersion'] = version
    plist_data['CFBundleShortVersionString'] = version

    # Write the updated plist back to the file
    with open(file_path, 'wb') as fp:
        plistlib.dump(plist_data, fp)

    return True

def create_zanshin_update(tarball_path, app_path, update_script_path, info_dict, debug, output_path="zanshin_update.tar.xz"):
    try:
        # Ensure paths are absolute
        tarball_path = Path(tarball_path).absolute()
        app_path = Path(app_path).absolute()
        output_path = Path(output_path).absolute()

        # Create a temporary file for info.json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_json:
            json.dump(info_dict, temp_json, indent=2)
            temp_json_path = temp_json.name
            temp_json_filename = os.path.basename(temp_json_path)

        # Build the gtar command with transforms to:
        # 1. Rename files to their final names
        # 2. Put everything inside an "update" directory
        gtar_cmd = [
            "gtar",
            # First transform renames files to their desired names
            "--transform", f"s|{os.path.basename(tarball_path)}|update.tar.xz|",
            "--transform", f"s|{temp_json_filename}|info.json|",
            # Second transform places everything in the update directory
            "--transform", "s|^|update/|",
            "-cf", "-",  # Output to stdout
            "-C", str(os.path.dirname(tarball_path)), os.path.basename(tarball_path),             # Include delta update
            "-C", str(os.path.dirname(app_path)), os.path.basename(app_path),                     # Include app bundle
            "-C", str(os.path.dirname(update_script_path)), os.path.basename(update_script_path),
            "-C", str(os.path.dirname(temp_json_path)), temp_json_filename                        # Include info.json
        ]

        # Compress with xz using maximum settings
        if not debug:
            xz_cmd = ["xz", "-T0", "-9e"]
        else:
            xz_cmd = ["xz", "-T0"]

        # Create the archive with piping
        with open(output_path, 'wb') as outfile:
            tar_process = subprocess.Popen(gtar_cmd, stdout=subprocess.PIPE)
            subprocess.run(xz_cmd, stdin=tar_process.stdout, stdout=outfile, check=True)
            tar_process.stdout.close()
            return_code = tar_process.wait()
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, gtar_cmd)

        # Clean up temporary files
        os.remove(temp_json_path)
        print(f"Successfully created {output_path}")
        return True
    except Exception as e:
        print(f"Error creating archive: {str(e)}")
        return False