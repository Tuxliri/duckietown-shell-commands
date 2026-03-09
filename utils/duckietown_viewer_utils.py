import glob
import json
import os
import platform
import re
import subprocess
import sys
import time
from threading import Thread
from types import SimpleNamespace
from typing import List, Optional, Union, Dict

import dockertown
import requests
import webbrowser
from dockertown import Container
from dockertown import DockerClient
from dockertown.exceptions import NoSuchContainer
from dt_data_api import DataClient

import dt_shell
from dt_shell import dtslogger, DTShell, UserError
from utils.docker_utils import get_client, get_registry_to_use, pull_image
from utils.duckietown_utils import USER_DATA_DIR, get_distro
from utils.misc_utils import versiontuple, random_string
from utils.networking_utils import get_duckiebot_ip

APP_NAME = "duckietown-viewer"
DCSS_SPACE_NAME = "public"
DCSS_APP_DIR = f"assets/{APP_NAME}/"
DCSS_APP_RELEASES_DIR = f"assets/{APP_NAME}/releases/"
APP_LOCAL_DIR = os.path.join(USER_DATA_DIR, APP_NAME)
APP_RELEASES_DIR = os.path.join(APP_LOCAL_DIR, "releases")

AVAHI_SOCKET = "/var/run/avahi-daemon/socket"
SUPPORTED_OS_FAMILIES = ("linux", "macos", "windows")

WindowArgs = Dict[str, Union[int, float, str]]


def linux_path_to_windows(path: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["wslpath", "-w", path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_installed_windows_app_path() -> Optional[str]:
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "echo %LOCALAPPDATA%"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return None
        windows_path = result.stdout.strip()
        result2 = subprocess.run(
            ["wslpath", windows_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result2.returncode != 0:
            return None
        wsl_path = result2.stdout.strip()
        search_dir = os.path.join(wsl_path, "Programs", APP_NAME)
        pattern = os.path.join(search_dir, "*.exe")
        matches = [
            file for file in glob.glob(pattern)
            if "uninstall" not in file.lower()
        ]
        return matches[0] if matches else None
    except Exception:
        return None


def get_os_family() -> str:
    if os.path.exists("/proc/version"):
        with open("/proc/version", "r") as f:
            if "microsoft" in f.read().lower():
                return "windows"
    if sys.platform.startswith('linux'):
        return "linux"
    elif sys.platform.startswith('win32') or sys.platform.startswith('cygwin'):
        return "windows"
    elif sys.platform.startswith('darwin'):
        return "macos"


def resolve_os_family(os_family: str = "", browser: bool = False) -> str:
    if os_family:
        if browser:
            raise UserError("You cannot use -os/--os-family and --browser together.")
        if os_family not in SUPPORTED_OS_FAMILIES:
            raise UserError(
                f"Unsupported os-family '{os_family}'. "
                f"Supported values are: {', '.join(SUPPORTED_OS_FAMILIES)}."
            )
        return os_family
    os_family = get_os_family()
    machine = platform.machine()
    if machine.lower() in ("aarch64", "arm64"):
        os_family += "-arm64"
    return os_family


def get_latest_version(os_family: str = "") -> Optional[str]:
    # create storage client
    client = DataClient()
    storage = client.storage(DCSS_SPACE_NAME)
    # get latest version
    latest_version_obj = os.path.join(DCSS_APP_DIR, f"latest-{os_family}")
    try:
        download = storage.download(latest_version_obj)
        download.join()
    except FileNotFoundError:
        return None
    return download.data.decode("ascii").strip()


def get_all_installed_releases(os_family: str = "") -> List[str]:
    app_dir = os.path.join(APP_RELEASES_DIR, f"*-{os_family}")
    dirs = glob.glob(app_dir)
    version_regex = r"v([0-9]+)\.([0-9]+)\.([0-9]+)"
    version_pattern = re.compile(version_regex)
    is_release_dir = lambda fp: os.path.isdir(fp) and version_pattern.match(os.path.basename(fp))
    return list(map(lambda p: os.path.basename(p)[1:], filter(is_release_dir, dirs)))


def get_most_recent_version_installed(os_family: str = "") -> Optional[str]:
    releases = get_all_installed_releases(os_family)
    release = None
    for r in releases:
        if release is None or versiontuple(r) > versiontuple(release):
            release = r
    if release is None:
        return None
    split_release = release.split("-")
    return split_release[0]


def get_path_to_install(version: str, os_family: str = ""):
    app_dir = os.path.join(APP_RELEASES_DIR, f"v{version}-{os_family}")
    if not os.path.isdir(app_dir):
        app_dir = None
    return app_dir


def get_path_to_binary(version: str, os_family: str = ""):
    app_dir = get_path_to_install(version, os_family)
    if app_dir is None:
        return None
    if os_family == "macos":
        return os.path.join(app_dir, "Duckietown Viewer.app")
    if os_family == "linux":
        ext = "AppImage"
    elif os_family == "windows":
        ext = "exe"
    else:
        raise ValueError(f"Unknown platform '{os_family}'")
    pattern = os.path.join(app_dir, f"{APP_NAME}-v{version}-*.{ext}")
    matching_files = glob.glob(pattern)
    if matching_files:
        return matching_files[0]
    return os.path.join(app_dir, f"{APP_NAME}-v{version}.{ext}")


def is_version_released(version: str, os_family: str = "") -> bool:
    # create storage client
    client = DataClient()
    storage = client.storage(DCSS_SPACE_NAME)
    # check whether the object exists
    release_obj = remote_zip_obj(version, os_family)
    try:
        storage.head(release_obj)
        return True
    except FileNotFoundError:
        return False


def remote_zip_obj(version: str, os_family: str = ""):
    return os.path.join(DCSS_APP_RELEASES_DIR, f"{APP_NAME}-{version}-{os_family}.zip")


def mark_as_latest_version(token: str, version: str, os_family: str):
    # create storage client
    client = DataClient(token)
    storage = client.storage(DCSS_SPACE_NAME)
    # get latest version
    latest_version_obj = os.path.join(DCSS_APP_DIR, f"latest-{os_family}")
    upload = storage.upload(version.encode("ascii"), latest_version_obj)
    upload.join()


def ensure_duckietown_viewer_installed(os_family: str = "", log_prefix: str = ""):
    shell: DTShell = dt_shell.shell
    log_prefix = log_prefix or " > "

    # make sure the app is not already installed
    installed_version: Optional[str] = get_most_recent_version_installed(os_family)
    # get latest version available on the DCSS
    latest: Optional[str] = get_latest_version(os_family)
    if latest is None:
        dtslogger.error(f"{log_prefix}No version available for installation.")
        return
    # compare installed and latest versions
    if installed_version:
        if installed_version == latest:
            return
        os.remove(get_path_to_binary(installed_version, os_family))
        os.rmdir(get_path_to_install(installed_version, os_family))
    # download new version
    app_dir = os.path.join(APP_RELEASES_DIR, f"v{latest}-{os_family}")

    dtslogger.info(f"{log_prefix}Downloading version v{latest}...")
    os.makedirs(app_dir, exist_ok=True)
    zip_remote = remote_zip_obj(latest, os_family)
    zip_local = os.path.join(app_dir, f"v{latest}.zip")
    shell.include.data.get.command(
        shell,
        [],
        parsed=SimpleNamespace(
            object=[zip_remote],
            file=[zip_local],
            space=DCSS_SPACE_NAME,
        )
    )
    dtslogger.info(f"{log_prefix}Download completed.")

    # install
    dtslogger.info(f"{log_prefix}Installing...")
    subprocess.check_call(["unzip", f"v{latest}.zip"], cwd=app_dir)
    # On macOS, extract the .app from the DMG
    if os_family == "macos":
        dmg_pattern = os.path.join(app_dir, "*.dmg")
        dmg_files = glob.glob(dmg_pattern)
        if dmg_files:
            dmg_file = dmg_files[0]
            dtslogger.info(f"{log_prefix}Mounting DMG...")
            # Mount the DMG
            result = subprocess.run(
                ["hdiutil", "attach", dmg_file, "-nobrowse"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Parse mount point from output
                mount_point = None
                for line in result.stdout.split("\n"):
                    if "/Volumes/" in line:
                        split_line = line.split("\t")
                        mount_point = split_line[-1].strip()
                        break
                if mount_point:
                    # Find .app in mounted volume
                    app_pattern = os.path.join(mount_point, "*.app")
                    app_files = glob.glob(app_pattern)
                    if app_files:
                        dtslogger.info(
                            f"{log_prefix}Extracting application..."
                        )
                        # Copy .app to installation directory
                        app_name = os.path.basename(app_files[0])
                        dest_app = os.path.join(app_dir, app_name)
                        subprocess.check_call(
                            ["cp", "-R", app_files[0], dest_app]
                        )
                    # Unmount the DMG
                    dtslogger.info(f"{log_prefix}Unmounting DMG...")
                    subprocess.run(
                        ["hdiutil", "detach", mount_point],
                        capture_output=True
                    )
                # Remove the DMG file
                os.remove(dmg_file)
    if os_family == "windows":
        # ensure the installer is executable (needed in WSL)
        installer = get_path_to_binary(latest, os_family)
        if installer and os.path.exists(installer):
            installer_status = os.stat(installer)
            os.chmod(installer, installer_status.st_mode | 0o111)
        # run the NSIS installer silently so the app ends up in %LOCALAPPDATA%
        dtslogger.info(
            f"{log_prefix}Running Windows installer silently..."
        )
        subprocess.check_call([installer, "/S"])
        dtslogger.info(f"{log_prefix}Windows installer completed.")
    # clean up
    dtslogger.info(f"{log_prefix}Removing temporary files...")
    os.remove(zip_local)
    # ---
    dtslogger.info(f"{log_prefix}Installation completed successfully!")


def launch_viewer(app: str, *, os_family: str = "", robot: Optional[str] = None, verbose: bool = False, fullscreen: bool = False, menu: bool = False, on_top: bool = False, enable_hardware_acceleration: bool = False, browser: bool = False, window_args: Optional[WindowArgs] = None) \
        -> 'DuckietownViewerInstance':
    viewer = DuckietownViewerInstance(os_family, verbose)
    viewer.start(app, robot, fullscreen, menu, on_top, enable_hardware_acceleration, browser, window_args=window_args)
    return viewer


class DuckietownViewerInstance:
    _BACKEND_DOCKER_IMAGE = "{registry}/duckietown/dt-duckietown-viewer:{distro}"
    _BACKEND_REMOTE_PORT = 8000
    _KNOWN_APPS = [
        "image_viewer",
        "keyboard_controller",
        "intrinsics_calibrator",
        "extrinsics_calibrator",
        "led_controller",
        "dashboard"
    ]

    def __init__(self, os_family: str = "", verbose: bool = False):
        self._os_family: str = os_family
        self._verbose: bool = verbose
        # internal state
        self._backend: Optional[Container] = None
        self._frontend: Optional[subprocess.Popen] = None
        self._backend_url: Optional[str] = None

    def start(self, app: str, robot: Optional[str], fullscreen: Optional[bool], menu: Optional[bool], on_top: Optional[bool], enable_hardware_acceleration: Optional[bool], browser: bool = False, window_args: Optional[WindowArgs] = None):
        if "url" not in window_args.keys():
            self._start_backend(app, robot)
            if not self._wait_backend_ready():
                self._backend.stop()
                return
        if browser:
            url = f"http://localhost:{self._host_port}/app/"
            if not webbrowser.open(url):
                dtslogger.warning("Could not open browser.")
            dtslogger.info(f"Navigate to {url}")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                dtslogger.info("Exiting...")
        else:
            self._start_frontend(fullscreen, menu, on_top, enable_hardware_acceleration, window_args or {})
            self._join_frontend()
        self._stop()

    def _start_backend(self, app: str, robot: str):
        import dt_shell
        # make sure the app is known
        if app not in self._KNOWN_APPS:
            raise ValueError(f"Unknown app '{app}'. Known apps are: {', '.join(self._KNOWN_APPS)}")
        # resolve IP address of the robot
        try:
            ip: str = get_duckiebot_ip(robot)
        except Exception:
            raise UserError(f"Could not resolve IP address for robot '{robot}'. Make sure the robot is online.")
        dtslogger.debug(f"Resolved IP address of '{robot}' to '{ip}'")
        # create docker client
        docker: DockerClient = get_client()
        # compile image name
        image = self._BACKEND_DOCKER_IMAGE.format(
            registry=get_registry_to_use(),
            distro=get_distro(dt_shell.shell).name
        )
        dtslogger.info(f"Checking for updates...")
        pull_image(image, docker)
        dtslogger.debug(f"Using image '{image}'")
        # create container
        container_name: str = f"duckietown-viewer-backend-{random_string()}"
        container_cfg: dict = {
            "name": container_name,
            "detach": True,
            "publish": [(0, self._BACKEND_REMOTE_PORT)],
            "volumes": [],
            "remove": True,
            "envs": {
                "DT_LAUNCHER": app,
                "VEHICLE_IP": ip,
                "VEHICLE_NAME": robot,
            }
        }
        # mount avahi socket (if it is available)
        if os.path.exists(AVAHI_SOCKET):
            container_cfg["volumes"].append((AVAHI_SOCKET, AVAHI_SOCKET))
        # run the container
        dtslogger.debug(f"Starting container with configuration:\n{json.dumps(container_cfg, indent=4)}")
        container: Container = docker.run(image, **container_cfg)
        # stop container when the shell is closed

        def _stop_container(_):
            try:
                dtslogger.debug(f"Stopping container '{container_name}'...")
                container.stop()
                dtslogger.debug(f"Container '{container_name}' stopped")
            except NoSuchContainer:
                dtslogger.warning(f"Could not stop container '{container_name}'")

        dt_shell.shell.on_shutdown(_stop_container)

        # in verbose mode we attach a log reader to the container
        if self._verbose:
            def _consume_container_logs():
                # consume logs
                print(dockertown.__version__)
                for (stream, line) in container.logs(follow=True, stream=True):
                    line = line.decode("utf-8")
                    print(line, end="")

            # start log reader
            log_reader = Thread(target=_consume_container_logs, daemon=True)
            log_reader.start()

        # save container
        self._backend = container

    def _wait_backend_ready(self) -> bool:
        container: Container = self._backend
        container_name: str = container.name
        dtslogger.debug(f"Waiting for container '{container_name}' to be ready...")

        # retrieve container's published port on the host
        container.reload()
        self._host_port: str = container.network_settings.ports[f"{self._BACKEND_REMOTE_PORT}/tcp"][0]["HostPort"]
        
        # use localhost with the published host port (more reliable across Docker versions)
        backend_url = f"localhost:{self._host_port}"
        dtslogger.debug(f"Container '{container_name}' is reachable at '{backend_url}'")
        # wait for the backend to be ready
        stime: float = time.time()
        timeout: float = 10
        while True:
            url: str = f"http://{backend_url}/"
            try:
                response = requests.get(url)
                dtslogger.debug(f"GET: {url}\n < {response.status_code} {response.reason}")
            except requests.exceptions.ConnectionError:
                # retry
                time.sleep(0.5)
                continue

            # ready
            if response.status_code == 200:
                dtslogger.debug(f"Container '{container_name}' is ready")
                self._backend_url = backend_url
                return True
            # timeout
            if time.time() - stime > timeout:
                dtslogger.error(f"Timeout reached ({timeout}s) while waiting for container '{container_name}'")
                return False
            # retry
            time.sleep(0.5)

    def _start_frontend(self, fullscreen: Optional[bool], menu: Optional[bool], on_top: Optional[bool], enable_hardware_acceleration: Optional[bool], args: WindowArgs):
        app_config = ["--no-sandbox"]
        if "url" not in args.keys():
            if self._backend_url is None:
                raise ValueError("Backend not ready. This should not have happened.")
            app_config.extend(["--url", f"http://{self._backend_url}/app/"])
        if fullscreen:
            app_config.append("--fullscreen")
        if menu:
            app_config.append("--menu")
        if on_top:
            app_config.append("--on-top")
        if enable_hardware_acceleration:
            app_config.append("--enable-hardware-acceleration")
        os_family = self._os_family
        if os_family == "windows":
            app_bin = get_installed_windows_app_path()
        else:
            app_bin = get_path_to_binary(get_most_recent_version_installed(os_family), os_family)
        # add extra arguments
        for k, v in args.items():
            app_config.append(f"--{k}={v}")
        # run the app
        dtslogger.info("Launching viewer...")
        # On macOS, use 'open' command for .app bundles
        if os_family == "macos" and app_bin.endswith(".app"):
            # -W flag makes open wait until the application exits
            app_cmd = ["open", "-W", app_bin, "--args"] + app_config
        else:
            app_cmd = [app_bin] + app_config
        dtslogger.debug(f"$ > {app_cmd}")
        self._frontend = subprocess.Popen(app_cmd)

    def _join_frontend(self):
        self._frontend.wait()
        dtslogger.info("Viewer closed. Exiting...")

    def _stop(self):
        if self._frontend is not None:
            self._frontend.terminate()
        if self._backend is not None:
            self._backend.stop()
