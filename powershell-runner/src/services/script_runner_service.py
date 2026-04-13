import re
import subprocess
import threading
import os

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.services.log_service import log_info, log_error, log_warning

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts')

# Timeout (seconds) for a single script execution.  Slightly below the
# orchestrator's HTTP timeout so the subprocess finishes first and a clean
# error response is returned instead of an HTTP timeout.
SCRIPT_PROCESS_TIMEOUT = int(os.environ.get('SCRIPT_PROCESS_TIMEOUT', '840'))


class ScriptRunnerService:
    def __init__(self, job_run_id, script_name, stop_words=None, params=None):
        self.job_run_id = job_run_id
        self.script_name = script_name
        self.stop_words = [w.lower() for w in (stop_words or [])]
        self.params = params or {}
        self._process = None
        self._stopped_by_word = None
        self._output_lines = []

    def run(self):
        script_path = self._resolve_script_path()
        log_info(f"Starting script: {self.script_name}", job_run_id=self.job_run_id)

        _SAFE_PARAM_NAME = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

        ps_args = []
        for key, value in self.params.items():
            if not _SAFE_PARAM_NAME.match(key):
                raise ValueError(f"Invalid parameter name: {key!r}")
            if isinstance(value, bool) or (isinstance(value, int) and value in (0, 1)):
                ps_args.append(f'-{key} ${str(bool(value)).lower()}')
            elif isinstance(value, str) and value.lower() in ('true', 'false'):
                ps_args.append(f'-{key} ${value.lower()}')
            else:
                safe_value = str(value).replace("'", "''")
                ps_args.append(f"-{key} '{safe_value}'")

        ps_command = f"& '{script_path}' {' '.join(ps_args)}"
        cmd = ['pwsh', '-NoProfile', '-NonInteractive', '-Command', ps_command]

        log_info(f"Running command: pwsh {script_path} ({len(ps_args)} params)", job_run_id=self.job_run_id)

        env = {**os.environ, 'NO_COLOR': '1'}
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

        stderr_reader = threading.Thread(
            target=self._read_stream,
            args=(self._process.stdout,),
            daemon=True,
        )
        stderr_reader.start()
        stderr_reader.join(timeout=SCRIPT_PROCESS_TIMEOUT)

        try:
            exit_code = self._process.wait(timeout=SCRIPT_PROCESS_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            msg = (f"Script '{self.script_name}' timed out after "
                   f"{SCRIPT_PROCESS_TIMEOUT}s – process killed")
            log_error(msg, stack_trace='', job_run_id=self.job_run_id)
            return {
                'completed': False,
                'exit_code': -1,
                'stopped_by_word': None,
                'timed_out': True,
                'output': self._output_lines,
            }

        if self._stopped_by_word:
            msg = (f"Script '{self.script_name}' terminated – "
                   f"stop word '{self._stopped_by_word}' detected in output")
            log_warning(msg, job_run_id=self.job_run_id)
            return {
                'completed': False,
                'exit_code': exit_code,
                'stopped_by_word': self._stopped_by_word,
                'output': self._output_lines,
            }

        if exit_code != 0:
            log_error(
                f"Script '{self.script_name}' exited with code {exit_code}",
                stack_trace='',
                job_run_id=self.job_run_id,
            )
        else:
            log_info(f"Script '{self.script_name}' completed successfully", job_run_id=self.job_run_id)

        return {
            'completed': exit_code == 0,
            'exit_code': exit_code,
            'stopped_by_word': None,
            'output': self._output_lines,
        }

    def _read_stream(self, stream):
        thread_local = ThreadLocalSingleton.instance().thread_local
        thread_local.job_run_id = self.job_run_id
        try:
            while True:
                line = stream.readline()
                if not line:
                    break

                line = _ANSI_RE.sub('', line.rstrip('\n\r'))
                if not line:
                    continue

                self._output_lines.append(line)
                # print(f"[ps1 output] {line}", flush=True)
                log_info(line, job_run_id=self.job_run_id)

                if self._contains_stop_word(line):
                    self._stopped_by_word = self._matching_stop_word(line)
                    log_warning(
                        f"Stop word '{self._stopped_by_word}' found – killing process",
                        job_run_id=self.job_run_id,
                    )
                    self._process.kill()
                    return
        except ValueError:
            pass

    def _contains_stop_word(self, line):
        lower = line.lower()
        return any(w in lower for w in self.stop_words)

    def _matching_stop_word(self, line):
        lower = line.lower()
        for w in self.stop_words:
            if w in lower:
                return w
        return None

    def _resolve_script_path(self):
        if not self.script_name.endswith('.ps1'):
            raise ValueError("Only .ps1 scripts are allowed")

        script_path = os.path.normpath(os.path.join(SCRIPTS_DIR, self.script_name))

        if not script_path.startswith(os.path.normpath(SCRIPTS_DIR)):
            raise ValueError("Invalid script path")

        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"Script not found: {self.script_name}")

        return script_path
