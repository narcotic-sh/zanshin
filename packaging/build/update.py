import subprocess
import json
import os
import shutil
from pathlib import Path
import pwd

#############################################################################################################################
# get_zanshin_application_support_path()
#############################################################################################################################

def get_zanshin_application_support_path():
    # Get the real home directory
    try:
        # Get the home directory from the password database (similar to libc::getpwuid)
        home_dir = pwd.getpwuid(os.getuid()).pw_dir
    except:
        # Fallback to environment variable if the above fails
        home_dir = os.environ.get('HOME', '')

    path = os.path.join(home_dir, 'Library', 'Application Support', 'Zanshin')
    return os.path.normpath(path)

#############################################################################################################################
# MarkerManager
#############################################################################################################################

class MarkerManager:
    """
    Manages update process markers to track progress and handle interrupted updates.
    Creates marker files in the application support directory to indicate the current
    stage of the update process.
    """

    def __init__(self, app_support):
        """
        Initialize the MarkerManager with the application support directory path.

        Args:
            app_support (str): Path to the application support directory
                                (e.g. ~/Library/Application Support/Zanshin)
        """
        self.app_support = Path(app_support)
        self.markers_dir = self.app_support / "update_markers"

        # Create markers directory if it doesn't exist
        os.makedirs(self.markers_dir, exist_ok=True)

    def create_marker(self, stage_name):
        """
        Create a marker file for the specified update stage.

        Args:
            stage_name (str): Name of the update stage
        """
        marker_path = self.markers_dir / f"{stage_name}.marker"
        with open(marker_path, 'w') as f:
            f.write(f"Update stage: {stage_name}")

    def delete_marker(self, stage_name):
        """
        Delete the marker file for the specified update stage.

        Args:
            stage_name (str): Name of the update stage
        """
        marker_path = self.markers_dir / f"{stage_name}.marker"
        if marker_path.exists():
            os.remove(marker_path)

    def has_marker(self, stage_name):
        """
        Check if a marker exists for the specified update stage.

        Args:
            stage_name (str): Name of the update stage

        Returns:
            bool: True if the marker exists, False otherwise
        """
        marker_path = self.markers_dir / f"{stage_name}.marker"
        return marker_path.exists()

    def get_active_markers(self):
        """
        Get a list of all active markers.

        Returns:
            list: List of marker stage names (without the .marker extension)
        """
        if not self.markers_dir.exists():
            return []

        markers = []
        for file in self.markers_dir.glob("*.marker"):
            markers.append(file.stem)

        return markers

    def clean_all_markers(self):
        """
        Remove all marker files.
        """
        if self.markers_dir.exists():
            for file in self.markers_dir.glob("*.marker"):
                os.remove(file)

    def handle_interrupted_update(self):
        """
        Handle an interrupted update by cleaning up markers and update files:
        1. Remove all marker files
        2. Remove the update directory if it exists
        3. Remove any files ending with "_update.tar.xz" in the app_support directory

        Returns:
            bool: True if an interrupted update was detected and cleaned up, False otherwise
        """
        markers = self.get_active_markers()

        if markers:
            # Clean up markers
            self.clean_all_markers()

            # Clean up update directory
            update_dir = self.app_support / "update"
            if update_dir.exists():
                shutil.rmtree(update_dir)

            # Remove any update tarballs in the app_support directory
            for file in self.app_support.glob("*_update.tar.xz"):
                try:
                    os.remove(file)
                    print(f"Removed update tarball: {file}")
                except Exception as e:
                    print(f"Failed to remove update tarball {file}: {e}")

            return True

        return False

    def progress_to_next_stage(self, current_stage, next_stage):
        """
        Progress from the current update stage to the next by removing the current
        marker and creating the next one.

        Args:
            current_stage (str): Name of the current update stage
            next_stage (str): Name of the next update stage
        """
        self.delete_marker(current_stage)
        self.create_marker(next_stage)

#############################################################################################################################
# clean_directory()
#############################################################################################################################

def clean_directory(directory_path, keep_items):
    # Ensure keep_items is a set for O(1) lookups
    keep_set = set(keep_items)

    # Get all items in the directory
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)

        # Skip if the item should be kept
        if item in keep_set:
            continue

        # Remove file or directory
        if os.path.isfile(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)

#############################################################################################################################
# main()
#############################################################################################################################

if __name__ == '__main__':

    # ~/Library/Application Support/Zanshin
    root = get_zanshin_application_support_path()

    marker_manager = MarkerManager(root)

    # Create installation marker
    marker_manager.create_marker("installing")

    # Delete the ready_for_install marker if it exists
    marker_manager.delete_marker("ready_for_install")

    # ~/Library/Application Support/Zanshin/update
    update_dir = (Path(root) / 'update').as_posix()

    # ./zanshin
    zanshin = (Path(root) / 'zanshin').as_posix()

    # ~/Library/Application Support/Zanshin/update/update.tar.xz
    update_tarball = (Path(update_dir) / 'update.tar.xz').as_posix()

    # /Applications/Zanshin.app
    old_app_bundle = '/Applications/Zanshin.app'
    new_app_bundle = (Path(update_dir) / 'Zanshin.app').as_posix()

    # Get version of update, update type
    info_file = (Path(update_dir) / 'info.json').as_posix()
    with open(info_file, 'r') as file:
        data = json.load(file)

    version = data['version']
    update_type = data['type']

    # Delta update
    if update_type == 'delta':

        # Remove just the src folder ; rest of files ('requirements.txt', 'VERSION', 'THIRD_PARTY_LICENSES') will get overwritten fully by rsyc with -w flag
        src = (Path(root) / 'zanshin' / 'src').as_posix()
        shutil.rmtree(src)

    # Full update
    elif update_type == 'full':

        # Remove everything except...
        clean_directory(zanshin, ['python_interpreter', 'media.db', 'settings.json'])

    # If ~/Library/Application Support/Zanshin/update/update.tar.xz exists (is unextracted)
    if os.path.exists(update_tarball):

        # Extract (multi-threaded)
        env = os.environ.copy()
        env['XZ_DEFAULTS'] = "-T 0"
        subprocess.run(['tar', '-xf', update_tarball, '-C', root], env=env, check=True)

    # If it doesn't exist (already extracted) then there will be a folder ~/Library/Application Support/Zanshin/update/zanshin that we can simply rsync
    else:
        folder_to_rsync = (Path(root) / 'update' / 'zanshin').as_posix()
        if os.path.exists(folder_to_rsync):
            subprocess.run(['rsync', '-a', '-W', '--inplace', folder_to_rsync, root])

    # Remove old app bundle /Applications/Zanshin.app
    if os.path.exists(old_app_bundle):
        shutil.rmtree(old_app_bundle)

    # Copy (ditto) new app bundle
    subprocess.run(["ditto", new_app_bundle, old_app_bundle], check=True)

    # Remove update folder
    shutil.rmtree(update_dir)

    # Update complete, clean up all markers
    marker_manager.clean_all_markers()