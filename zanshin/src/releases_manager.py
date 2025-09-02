import requests

class ZanshinReleaseManager:
    def __init__(self):
        self.owner = "narcotic-sh"
        self.repo = "zanshin"
        self.releases = self._fetch_all_releases()

    def _fetch_all_releases(self):
        """Fetch all releases from GitHub and store them internally"""

        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"

        try:
            response = requests.get(url)
            response.raise_for_status()

            releases_data = response.json()
            all_releases = []

            for release_data in releases_data:
                version = release_data["tag_name"]
                assets_dict = {
                    "full": None,
                    "delta": None,
                    "pkg": None
                }

                # Categorize assets based on filename patterns
                for asset in release_data["assets"]:
                    asset_name = asset["name"]
                    browser_download_url = asset["browser_download_url"]
                    asset_api_url = asset["url"]
                    asset_id = asset["id"]

                    if "_full_update.tar.xz" in asset_name:
                        assets_dict["full"] = {
                            "browser_download_url": browser_download_url,
                            "api_url": asset_api_url,
                            "id": asset_id,
                            "name": asset_name
                        }
                    elif "_delta_update.tar.xz" in asset_name:
                        assets_dict["delta"] = {
                            "browser_download_url": browser_download_url,
                            "api_url": asset_api_url,
                            "id": asset_id,
                            "name": asset_name
                        }
                    elif asset_name.endswith(".pkg"):
                        assets_dict["pkg"] = {
                            "browser_download_url": browser_download_url,
                            "api_url": asset_api_url,
                            "id": asset_id,
                            "name": asset_name
                        }

                release_info = {
                    "version": version,
                    "assets": assets_dict
                }

                all_releases.append(release_info)

            # Sort releases by version (newest first)
            all_releases.sort(key=self._version_key, reverse=True)
            return all_releases

        except requests.exceptions.RequestException as e:
            print(f"Error fetching release information: {e}")
            return []

    def _version_key(self, release):
        """Convert version string to tuple for proper sorting"""
        version = release["version"]
        # Handle versions with and without patch number
        parts = version.split('.')

        # Convert all parts to integers for comparison
        version_tuple = tuple(int(part) for part in parts)

        # Ensure 4 components for consistent sorting (add 0 for missing patch number)
        if len(version_tuple) == 3:
            version_tuple = version_tuple + (0,)

        return version_tuple

    def get_update_info(self, current_version):
        """
        Check if an update is available and determine whether to use delta or full update

        Returns:
            dict: Contains update info if available, or None if no update available
                {
                    "version": "new_version",
                    "update_type": "delta|full",
                    "download_url": "url_to_appropriate_update",
                    "filename": "name_of_the_file"
                }
        """
        if not self.releases or len(self.releases) == 0:
            return None

        # If we have less than 2 releases, we can't determine "second latest"
        if len(self.releases) < 2:
            latest_release = self.releases[0]
            current_version_tuple = self._version_string_to_tuple(current_version)
            latest_version_tuple = self._version_string_to_tuple(latest_release["version"])

            if latest_version_tuple > current_version_tuple:
                if latest_release["assets"]["full"] is not None:
                    return {
                        "version": latest_release["version"],
                        "update_type": "full",
                        "download_url": latest_release["assets"]["full"]["api_url"],
                        "filename": latest_release["assets"]["full"]["name"]
                    }
            return None

        # We have at least 2 releases
        latest_release = self.releases[0]
        second_latest_release = self.releases[1]

        current_version_tuple = self._version_string_to_tuple(current_version)
        latest_version_tuple = self._version_string_to_tuple(latest_release["version"])
        second_latest_version_tuple = self._version_string_to_tuple(second_latest_release["version"])

        # No update needed
        if current_version_tuple >= latest_version_tuple:
            return None

        # Current version is the second latest version - use delta update
        if current_version_tuple == second_latest_version_tuple:
            if latest_release["assets"]["delta"] is not None:
                return {
                    "version": latest_release["version"],
                    "update_type": "delta",
                    "download_url": latest_release["assets"]["delta"]["api_url"],
                    "filename": latest_release["assets"]["delta"]["name"]
                }
            # Fall back to full update if delta is not available
            elif latest_release["assets"]["full"] is not None:
                return {
                    "version": latest_release["version"],
                    "update_type": "full",
                    "download_url": latest_release["assets"]["full"]["api_url"],
                    "filename": latest_release["assets"]["full"]["name"]
                }
            else:
                return None

        # Current version is older than second latest - use full update
        if latest_release["assets"]["full"] is not None:
            return {
                "version": latest_release["version"],
                "update_type": "full",
                "download_url": latest_release["assets"]["full"]["api_url"],
                "filename": latest_release["assets"]["full"]["name"]
            }
        return None

    def _version_string_to_tuple(self, version):
        """Convert version string to tuple for comparison"""
        parts = version.split('.')
        version_tuple = tuple(int(part) for part in parts)

        # Ensure 4 components for consistent comparison
        if len(version_tuple) == 3:
            version_tuple = version_tuple + (0,)

        return version_tuple

    def get_all_releases(self):
        """Return all releases"""
        return self.releases

    def get_latest_version(self):
        """Return the latest version string if available"""
        if self.releases:
            return self.releases[0]["version"]
        return None

    def download_asset(self, asset_url, save_path):
        """
        Download an asset from GitHub releases using the API

        Args:
            asset_url: The GitHub API URL for the asset
            save_path: Where to save the downloaded file

        Returns:
            bool: True if download succeeded, False otherwise
        """
        headers = {
            "Accept": "application/octet-stream",
        }

        try:
            response = requests.get(asset_url, headers=headers, stream=True)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True

        except requests.exceptions.RequestException as e:
            print(f"Error downloading asset: {e}")
            return False