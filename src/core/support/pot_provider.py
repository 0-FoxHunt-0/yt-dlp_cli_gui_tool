import subprocess
import logging
import time
import os
from urllib import request as urllib_request
from urllib import error as urllib_error
import socket
from urllib.parse import urlparse
import importlib.util


class POTProviderManager:
    """Manages the bgutil PO Token provider lifecycle and yt-dlp wiring.

    Responsibilities:
    - Detect Docker CLI and daemon availability
    - Ensure the provider container exists and is running (start or create)
    - Poll the HTTP provider until ready before wiring yt-dlp extractor args
    - Fail fast with clear logs and allow the caller to fall back gracefully

    Reference: https://github.com/Brainicism/bgutil-ytdlp-pot-provider
    """

    def __init__(self, config):
        self.config = config

    def _get_docker_env(self) -> dict:
        """Get environment with Docker paths added to PATH."""
        env = os.environ.copy()
        current_path = env.get('PATH', '')

        # Add Docker Desktop paths if not already in PATH
        docker_paths = [
            'C:\\Program Files\\Docker\\Docker\\resources\\bin',
            'C:\\Program Files\\Docker\\cli-plugins',
        ]

        for docker_path in docker_paths:
            if docker_path not in current_path:
                env['PATH'] = docker_path + os.pathsep + current_path

        return env

    def docker_available(self) -> bool:
        """Return True if Docker CLI exists and daemon is reachable."""
        env = self._get_docker_env()

        try:
            ver = subprocess.run(['docker', '--version'], capture_output=True, timeout=5, env=env)
            if ver.returncode != 0:
                return False
            info = subprocess.run(['docker', 'info'], capture_output=True, timeout=8, env=env)
            return info.returncode == 0
        except Exception as e:
            logging.info(f"Docker not available or daemon unreachable: {e}")
            return False

    def ensure_container(self, image: str, container_name: str, port: int) -> str:
        """Ensure the POT provider Docker container is running; return base_url.

        Behavior:
        - If running: reuse
        - If exists but stopped: start
        - Otherwise: pull image and run new container with required port mapping
        """
        env = self._get_docker_env()

        # Check running
        try:
            ps = subprocess.run(['docker', 'ps', '--filter', f'name=^{container_name}$', '--format', '{{.Status}}'],
                                capture_output=True, timeout=8, env=env)
            if ps.returncode == 0 and ps.stdout:
                status = ps.stdout.decode('utf-8', errors='replace').strip()
                if status:
                    logging.info(f"POT provider container '{container_name}' already running: {status}")
                    return f"http://127.0.0.1:{port}"
        except Exception:
            pass

        # Exists but stopped?
        try:
            inspect = subprocess.run(['docker', 'ps', '-a', '--filter', f'name=^{container_name}$', '--format', '{{.ID}}'],
                                     capture_output=True, timeout=8, env=env)
            exists = bool(inspect.returncode == 0 and inspect.stdout and inspect.stdout.strip())
        except Exception:
            exists = False

        if exists:
            up = subprocess.run(['docker', 'start', container_name], capture_output=True, timeout=15, env=env)
            if up.returncode != 0:
                stderr = up.stderr.decode('utf-8', errors='replace') if up.stderr else ''
                raise Exception(f"Failed to start existing POT container: {stderr}")
            logging.info(f"Started existing POT container '{container_name}'")
        else:
            pull = subprocess.run(['docker', 'pull', image], capture_output=True, timeout=600, env=env)
            if pull.returncode != 0:
                stderr = pull.stderr.decode('utf-8', errors='replace') if pull.stderr else ''
                raise Exception(f"Failed to pull POT image '{image}': {stderr[:200]}")

            run = subprocess.run([
                'docker', 'run', '--name', container_name, '-d',
                '-p', f'{port}:{port}', '--init', '--restart', 'unless-stopped', image
            ], capture_output=True, timeout=30, env=env)
            if run.returncode != 0:
                stderr = run.stderr.decode('utf-8', errors='replace') if run.stderr else ''
                raise Exception(f"Failed to run POT container: {stderr[:200]}")
            logging.info(f"Started new POT provider container '{container_name}' on port {port}")

        return f"http://127.0.0.1:{port}"

    def _log_docker_diagnostics(self, container_name: str, port: int) -> None:
        """Collect and log basic docker diagnostics to help troubleshoot issues."""
        env = self._get_docker_env()

        try:
            ctx = subprocess.run(['docker', 'context', 'show'], capture_output=True, timeout=5, env=env)
            if ctx.returncode == 0 and ctx.stdout:
                logging.info(f"Docker context: {ctx.stdout.decode('utf-8', errors='replace').strip()}")
        except Exception:
            pass

        try:
            ps = subprocess.run(['docker', 'ps', '-a', '--filter', f'name=^{container_name}$', '--format', '{{.ID}} {{.Status}} {{.Ports}}'],
                                capture_output=True, timeout=8, env=env)
            if ps.returncode == 0 and ps.stdout:
                logging.info(f"Container ps: {ps.stdout.decode('utf-8', errors='replace').strip()}")
        except Exception:
            pass

        try:
            insp = subprocess.run(['docker', 'inspect', container_name, '--format', '{{json .State}}'], capture_output=True, timeout=8, env=env)
            if insp.returncode == 0 and insp.stdout:
                logging.info(f"Container state: {insp.stdout.decode('utf-8', errors='replace').strip()}")
        except Exception:
            pass

        try:
            portmap = subprocess.run(['docker', 'port', container_name, str(port)], capture_output=True, timeout=5, env=env)
            if portmap.returncode == 0 and portmap.stdout:
                logging.info(f"Container port mapping: {portmap.stdout.decode('utf-8', errors='replace').strip()}")
        except Exception:
            pass

        try:
            logs = subprocess.run(['docker', 'logs', '--tail', '100', container_name], capture_output=True, timeout=10, env=env)
            if logs.stdout:
                logging.info("Last 100 lines of POT provider logs:\n" + logs.stdout.decode('utf-8', errors='replace'))
            if logs.stderr:
                logging.info("POT provider stderr:\n" + logs.stderr.decode('utf-8', errors='replace'))
        except Exception as e:
            logging.info(f"Could not read container logs: {e}")

    def stop_container_if_configured(self) -> None:
        """Stop the provider container on application exit if configured."""
        pot_cfg = self.config.get('pot_provider', {}) or {}
        if not pot_cfg.get('enabled', True) or not pot_cfg.get('stop_on_exit', True):
            return
        container = pot_cfg.get('docker_container_name', 'bgutil-provider')
        env = self._get_docker_env()

        try:
            # Only stop if running
            ps = subprocess.run(['docker', 'ps', '--filter', f'name=^{container}$', '--format', '{{.ID}}'],
                                capture_output=True, timeout=6, env=env)
            if ps.returncode == 0 and ps.stdout and ps.stdout.strip():
                subprocess.run(['docker', 'stop', '-t', '5', container], capture_output=True, timeout=20, env=env)
                logging.info(f"Stopped POT provider container '{container}' on exit")
        except Exception as e:
            logging.info(f"Could not stop POT provider container '{container}': {e}")

    def wait_http_ready(self, base_url: str, timeout_sec: int = 45) -> bool:
        """Wait for provider to accept connections.

        Strategy:
        1) Raw TCP connect to host:port
        2) HTTP GET on /health then /
        Accept any HTTP status (< 500). Only network failures cause retry.
        """
        parsed = urlparse(base_url)
        host = parsed.hostname or '127.0.0.1'
        port = parsed.port or 4416

        deadline = time.time() + timeout_sec
        delay = 0.3
        roots = [base_url.rstrip('/') + '/health', base_url.rstrip('/')]

        while time.time() < deadline:
            # 1) TCP probe
            try:
                with socket.create_connection((host, port), timeout=2.5):
                    return True
            except Exception:
                pass

            # 2) HTTP probe
            for url in roots:
                try:
                    req = urllib_request.Request(url, method='GET')
                    with urllib_request.urlopen(req, timeout=3) as resp:
                        # Consider any non-5xx status as ready
                        if 100 <= resp.status < 500:
                            return True
                except urllib_error.URLError:
                    pass
                except Exception:
                    pass

            time.sleep(delay)
            delay = min(delay * 1.5, 2.0)
        return False

    def maybe_enable_provider(self, options: dict) -> str | None:
        """Attempt to enable POT provider; fallback silently if not possible.

        Returns the base_url string if enabled successfully; otherwise None.
        """
        pot_cfg = self.config.get('pot_provider', {}) or {}
        if not pot_cfg or not pot_cfg.get('enabled', True):
            logging.info("POT provider disabled in config; proceeding without PO tokens")
            return None

        if not self.docker_available():
            logging.info("Docker not available; skipping POT provider integration")
            return None

        image = pot_cfg.get('docker_image', 'brainicism/bgutil-ytdlp-pot-provider')
        container = pot_cfg.get('docker_container_name', 'bgutil-provider')
        port = int(pot_cfg.get('docker_port', 4416))
        base_url = pot_cfg.get('base_url', f'http://127.0.0.1:{port}')

        # Ensure container running
        base_url = self.ensure_container(image, container, port)
        timeout_cfg = 0
        try:
            timeout_cfg = int(pot_cfg.get('readiness_timeout_secs', 45))
        except Exception:
            timeout_cfg = 45
        if not self.wait_http_ready(base_url, timeout_sec=timeout_cfg):
            raise Exception("POT provider HTTP server did not become ready in time")

        # Wire yt-dlp extractor args
        ex_args = options.setdefault('extractor_args', {})
        # Plugin expects list-of-strings exactly like CLI: --extractor-args "youtubepot-bgutil_http:base_url=..."
        pot_args_list = [f'base_url={base_url}']
        # Respect config for disable_innertube
        if pot_cfg.get('disable_innertube', True):
            pot_args_list.append('disable_innertube=1')
        ex_args['youtubepot-bgutil_http'] = pot_args_list
        # Back-compat legacy key in case older plugin variants check it
        ex_args['youtubepot-bgutilhttp'] = pot_args_list[:]

        yt_args = ex_args.setdefault('youtube', {})
        if 'player_client' not in yt_args:
            yt_args['player_client'] = ['default', 'mweb']

        # Preflight: try multiple endpoints and log basic headers
        preflight_paths = ['/health', '/version', '/']
        preflight_ok = False
        for path in preflight_paths:
            try:
                req = urllib_request.Request(base_url.rstrip('/') + path, method='GET')
                with urllib_request.urlopen(req, timeout=3) as resp:
                    server_hdr = resp.headers.get('Server') or resp.headers.get('server') or 'unknown'
                    logging.info(f"POT provider HTTP preflight OK path={path} (status {resp.status}, server={server_hdr})")
                    preflight_ok = True
                    break
            except Exception as e:
                logging.info(f"POT provider HTTP preflight path={path} failed (still proceeding): {e}")

        if not preflight_ok:
            # Gather docker diagnostics to help the user
            container = pot_cfg.get('docker_container_name', 'bgutil-provider')
            try:
                # pot_cfg is available in scope; if not, fallback to default name
                pass
            except Exception:
                container = 'bgutil-provider'
            try:
                self._log_docker_diagnostics(container, port)
            except Exception:
                pass

        # Log configured provider keys and values to confirm wiring
        try:
            configured = {k: ex_args.get(k) for k in ex_args.keys() if k.startswith('youtubepot')}
            logging.info(f"Configured youtubepot extractor_args: {configured}")
        except Exception:
            pass

        logging.info(f"POT provider enabled via Docker at {base_url}")
        logging.info("POT provider configured with disable_innertube=%s" % ("1" if pot_cfg.get('disable_innertube', False) else "0"))

        # Log HTTP request stack availability for the GetPOT plugin
        try:
            stacks = []
            for mod, label in [("requests", "requests"), ("curl_cffi", "curl_cffi"), ("httpx", "httpx"), ("urllib3", "urllib3")]:
                if importlib.util.find_spec(mod) is not None:
                    stacks.append(label)
            if stacks:
                logging.info(f"Available HTTP stacks for GetPOT: {', '.join(stacks)}")
            else:
                logging.info("No optional HTTP stacks detected (requests/curl_cffi/httpx). GetPOT may not configure handlers.")
        except Exception:
            pass
        return base_url


