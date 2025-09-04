# Have uv and bun installed
# uv pip install requests beautifulsoup4
# brew install cmake fd gnu-tar

# If new Python packages are added, make sure to run print_packages.py and update them in THIRD_PARTY_LICENSES:
# python print_packages.py

import os
from pathlib import Path
import subprocess
import argparse
import shutil
from build_misc import download_file, get_and_install_uv, build_pkg, create_zanshin_update, update_version_plist, delete_path, get_ffmpeg_download_links

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A script that requires a version argument')
    parser.add_argument('--version', required=True, help='Specify the version number')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--notarize', action='store_true', help='Submit built pkg for notarization')
    parser.add_argument('--clean', action='store_true', help='Clean build artifacts before building')
    args = parser.parse_args()

    version = args.version
    debug = args.debug
    notarize = args.notarize
    clean = args.clean

    ###########
    ## Paths ##
    ###########

    # root (./)
    root = Path(__file__).parent.parent.parent.as_posix()

    # ./launcher
    launcher = (Path(root) / "launcher").as_posix()

    # ./launcher/src-tauri
    src_tauri = (Path(launcher) / "src-tauri").as_posix()

    # ./zanshin
    zanshin = (Path(root) / "zanshin").as_posix()

    # ./zanshin/third_party
    third_party = (Path(zanshin) / "third_party").as_posix()

     # ./zanshin/src/ui
    ui = (Path(zanshin) / "src" / "ui").as_posix()

    # ./packaging/build
    build = (Path(root) / "packaging" / "build").as_posix()

    # ./packaging/dist
    dist = (Path(root) / "packaging" / "dist").as_posix()

    ###########
    ## Clean ##
    ###########

    if clean:
        paths_to_delete = [
            os.path.join(build, 'macho_files.txt'),        # ./packaging/build/macho_files.txt
            os.path.join(build, 'Zanshin'),                # ./packaging/build/Zanshin
            dist,                                          # ./packaging/dist/
            os.path.join(zanshin, 'python_interpreter'),   # ./zanshin/python_interpreter
            os.path.join(zanshin, 'src', 'ui_dist'),       # ./zanshin/src/ui_dist
            os.path.join(ui, 'node_modules'),              # ./zanshin/src/ui/node_modules
            third_party,                                   # ./zanshin/third_party
            os.path.join(zanshin, 'THIRD_PARTY_LICENSES')  # ./zanshin/THIRD_PARTY_LICENSES
        ]
        for path in paths_to_delete:
            delete_path(path)

    if not os.path.exists(dist):
        Path(dist).mkdir()

    if not os.path.exists(third_party):
        Path(third_party).mkdir()

    # Temporarily copy THIRD_PARTY_LICENSES to ./zanshin
    third_party_src = os.path.join(build, 'THIRD_PARTY_LICENSES')
    third_party_dst = os.path.join(zanshin, 'THIRD_PARTY_LICENSES')
    shutil.copy2(third_party_src, third_party_dst)

    ########################
    ## Set version number ##
    ########################

    print(f'Setting version {version}')

    # ./packaging/build/Info.plist
    info_plist = (Path(root) / "packaging" / "build" / "Info.plist").as_posix()
    update_version_plist(info_plist, version)

    # ./zanshin/VERSION
    VERSION = (Path(zanshin) / "VERSION").as_posix()
    with open(VERSION, 'w') as file:
        file.write(version)

    ###################################
    ## Build everything in ./zanshin ##
    ###################################

    # If ./packaging/dist/zanshin.tar.xz doesn't exist
    tarball = (Path(dist) / "zanshin.tar.xz").as_posix()
    if not os.path.exists(tarball):

        ###########################
        ## Fetch ffmpeg, ffprobe ##
        ###########################

        ffmpeg_folder = Path(third_party) / "ffmpeg"
        if not ffmpeg_folder.exists():
            ffmpeg_folder.mkdir(parents=True)

        # Fetch latest ffmpeg, ffprobe binaries
        binaries = get_ffmpeg_download_links()

        def dl_unzip_bin(name, url):
            zip = download_file(url, ffmpeg_folder.as_posix())
            subprocess.run(['unzip', '-q', zip, '-d', ffmpeg_folder.as_posix()])
            os.remove(zip)

        for name, url in binaries.items():
            bin = ffmpeg_folder / name
            if not bin.exists():
                print(f'Fetching {name}')
                dl_unzip_bin(name, url)

        ##############
        ## Fetch uv ##
        ##############

        uv_folder = Path(third_party) / "uv"

        if not os.path.exists(uv_folder):
            os.makedirs(uv_folder)
            get_and_install_uv(uv_folder)

        ###################################
        ## Build SvelteKit frontend code ##
        ###################################

        print('Building SvelteKit frontend code')

        subprocess.run(['bun', 'update'], cwd=ui, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(['bun', 'install'], cwd=ui, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(['bun', 'run', 'build'], cwd=ui, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        #######################################
        ## Python Interpreter & Dependancies ##
        #######################################

        python_interpreter = (Path(zanshin) / "python_interpreter").as_posix()

        if not os.path.exists(python_interpreter):
            print('Installing Python interpreter & dependancies')

            # Install Python interpreter
            subprocess.run(['uv', '-q', 'python', 'install', '-i', './python_interpreter', '3.11.13'], cwd=zanshin, check=True)

            # Install dependancies and Senko
            subprocess.run([
                'uv', '-q', 'pip', 'install',
                '--python', './python_interpreter/cpython-3.11.13-macos-aarch64-none/bin/python',
                '-r', 'requirements.txt', 'git+https://github.com/narcotic-sh/senko.git',
                '--break-system-packages'
            ], cwd=zanshin, check=True)

            # Install yt-dlp (latest pre-release version)
            subprocess.run([
                'uv', '-q', 'pip', 'install',
                '--python', './python_interpreter/cpython-3.11.13-macos-aarch64-none/bin/python',
                '--pre', 'yt-dlp',
                '--break-system-packages'
            ], cwd=zanshin, check=True)

        ##############################
        ## Codesign all executables ##
        ##############################

        if not os.path.exists(os.path.join(build, 'macho_finder')):
            subprocess.run(['clang++', '-std=c++17', '-O3', 'macho_finder.cpp', '-o', 'macho_finder'], cwd=build, check=True)

        dot_venv = (Path(zanshin) / ".venv").as_posix()

        print('Finding all binaries in zanshin/zanshin')
        subprocess.run(['./macho_finder', zanshin, '--ignore', dot_venv, '--ignore', ui], cwd=build, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Build the codesigner if it doesn't exist
        if not os.path.exists(os.path.join(build, 'macho_signer')):
            print('Building codesigner...')
            subprocess.run(['clang++', '-std=c++17', '-O3', 'macho_signer.cpp', '-o', 'macho_signer'], cwd=build, check=True)

        print("Codesigning all binaries in zanshin/zanshin")
        result = subprocess.run(['./macho_signer', 'macho_files.txt', '--entitlements', 'Zanshin.entitlements'], cwd=build, check=True)

        ###########################
        ## Create tar.xz for pkg ##
        ###########################

        print('Creating tarball for pkg')

        tar_cmd = f"gtar -cf - --exclude-from=zanshin/.tarignore -C zanshin --transform 's,^./,zanshin/,' . | xz -T0 {'-9e' if not debug else ''} > ./packaging/dist/zanshin.tar.xz"
        subprocess.run(tar_cmd, shell=True, cwd=root)

    #####################################
    ## Build Tauri Launcher executable ##
    #####################################

    print('Building Tauri launcher executable')

    subprocess.run(['bun', 'update'], cwd=launcher, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.run(['bun', 'install'], cwd=launcher, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.run(['cargo', 'update'], cwd=src_tauri, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.run(['bun', 'run', 'tauri', 'build', '--no-bundle'], cwd=launcher, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.run(['cp', 'launcher/src-tauri/target/release/zanshin', 'packaging/build/Zanshin'], cwd=root, check=True)

    ################
    ## Build .pkg ##
    ################

    print('Building .pkg')
    build_pkg(build, tarball, version, notarize)

    #######################
    ## Build full update ##
    #######################

    # If full update tarball doesn't exist
    tarball_full = (Path(dist) / "zanshin_full_update.tar.xz").as_posix()
    if not os.path.exists(tarball_full):
        print('Creating full update tarball')

        # Full update will contain everything except whatever is ignored in .tarignore
        tar_cmd = f"gtar -cf - --exclude-from=zanshin/.tarignore --exclude=python_interpreter -C zanshin --transform 's,^./,zanshin/,' . | xz -T0 {'-9e' if not debug else ''} > ./packaging/dist/zanshin_full_update.tar.xz"
        subprocess.run(tar_cmd, shell=True, cwd=root)

    info = {
        "version": version,
        "type": "full"
    }

    create_zanshin_update(
        tarball_path=os.path.join(build, "../dist/zanshin_full_update.tar.xz"),
        app_path=os.path.join(build, "../dist/Zanshin.app"),
        update_script_path=os.path.join(build, "update.py"),
        info_dict=info,
        debug=debug,
        output_path=os.path.join(build, f"../dist/zanshin_{version}_full_update.tar.xz")
    )

    os.remove(os.path.join(dist, "zanshin_full_update.tar.xz"))

    ########################
    ## Build delta update ##
    ########################

    # If delta update tarball doesn't exist
    tarball_delta = (Path(dist) / "zanshin_delta_update.tar.xz").as_posix()
    if not os.path.exists(tarball_delta):
        print('Creating delta update tarball')

        # Get all items in the zanshin directory
        all_items = os.listdir(zanshin)

        # Delta update will only contain src directory, requirements.txt, VERSION file, THIRD_PARTY_LICENSES file
        items_to_keep = ['src', 'requirements.txt', 'VERSION', 'THIRD_PARTY_LICENSES']
        items_to_exclude = [item for item in all_items if item not in items_to_keep]

        # Build the tar command with dynamic excludes
        exclude_args = " ".join([f"--exclude={item}" for item in items_to_exclude])

        tar_cmd = f"gtar -cf - --exclude-from=zanshin/.tarignore {exclude_args} -C zanshin --transform 's,^./,zanshin/,' . | xz -T0 {'-9e' if not debug else ''} > ./packaging/dist/zanshin_delta_update.tar.xz"

        # Run the command
        subprocess.run(tar_cmd, shell=True, cwd=root)

    info = {
        "version": version,
        "type": "delta"
    }

    create_zanshin_update(
        tarball_path=os.path.join(build, "../dist/zanshin_delta_update.tar.xz"),
        app_path=os.path.join(build, "../dist/Zanshin.app"),
        update_script_path=os.path.join(build, "update.py"),
        info_dict=info,
        debug=debug,
        output_path=os.path.join(build, f"../dist/zanshin_{version}_delta_update.tar.xz")
    )

    os.remove(os.path.join(dist, "zanshin_delta_update.tar.xz"))

    #############
    ## Cleanup ##
    #############

    # Remove THIRD_PARTY_LICENSES from zanshin/
    os.remove(third_party_dst)

    # Remove app bundle from dist
    shutil.rmtree(os.path.join(dist, "Zanshin.app"))
