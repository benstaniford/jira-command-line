"""Talk to Claudeck when jira runs inside it.

Claudeck puts a `claudeck` CLI on the PATH of every session it runs, shells included.
`claudeck status --json` says whether we are inside Claudeck (exit 0) and whether this
session may start others; `claudeck session new` opens a new Claude session in a tab
beside us, optionally in a fresh git worktree that Claudeck cuts and tracks.
"""
import json
import shutil
import subprocess


class Claudeck:
    STATUS_TIMEOUT = 10
    START_TIMEOUT = 60

    def __init__(self, run=subprocess.run, which=shutil.which):
        self._run = run
        self._which = which

    def installed(self) -> bool:
        return self._which("claudeck") is not None

    def status(self):
        """The `claudeck status --json` answer when running under Claudeck, else None.
        Anything going wrong (not installed, not inside it, app unreachable) is None."""
        if not self.installed():
            return None
        try:
            result = self._run(["claudeck", "status", "--json"], capture_output=True,
                               text=True, timeout=self.STATUS_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        try:
            status = json.loads(result.stdout)
        except ValueError:
            return None
        return status if isinstance(status, dict) and status.get("claudeck") else None

    def can_start_sessions(self) -> bool:
        """True when we are under Claudeck and its "Sessions may start sessions" is on."""
        status = self.status()
        return bool(status and status.get("mayStartSessions"))

    def new_session(self, prompt, directory=None, name=None, worktree=False, focus=False) -> str:
        """Start a Claude session in Claudeck and return its id (e.g. "s-4").
        The prompt goes over stdin so it never has to survive argv quoting.
        Raises with Claudeck's own reason when it refuses."""
        args = ["claudeck", "session", "new", "--prompt", "-"]
        if directory:
            args += ["--dir", directory]
        if name:
            args += ["--name", name]
        if worktree:
            args.append("--worktree")
        if focus:
            args.append("--focus")
        result = self._run(args, input=prompt, capture_output=True, text=True,
                           timeout=self.START_TIMEOUT)
        if result.returncode != 0:
            reason = (result.stderr or result.stdout or "").strip() or f"exit code {result.returncode}"
            raise Exception(f"Claudeck could not start a session: {reason}")
        return result.stdout.strip()
