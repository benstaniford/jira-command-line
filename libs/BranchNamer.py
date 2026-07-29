#scriptdoc: title="Shorten long Jira summaries into branch-sized names using Claude", tags="bt,work,git,ai"

import re
import shutil
import subprocess

class BranchNamer:
    """Turns a long issue summary into a short branch name fragment by asking
    the Claude CLI (in Haiku mode) for a few distinctive words.

    Every failure path - Claude not installed, non-zero exit, timeout, or a
    reply that doesn't look like a branch fragment - falls back to the caller's
    original summary, so branch creation never depends on Claude being there.
    """

    DEFAULT_MODEL = "haiku"
    DEFAULT_MAX_LENGTH = 40
    TIMEOUT_SECONDS = 60

    PROMPT = (
        "Shorten this software issue title into a git branch name fragment. "
        "Rules: 3-5 words max, lowercase, single hyphens between words, "
        "letters digits and hyphens only, keep the most distinctive words, "
        "no ticket ids, no quotes, no explanation. Reply with the fragment only."
        "\n\nTitle: {summary}"
    )

    # A plausible reply: lowercase words joined by single hyphens, nothing else
    FRAGMENT_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

    def __init__(self, config=None):
        config = config or {}
        self.model = config.get("branch_name_model", self.DEFAULT_MODEL)
        self.max_length = config.get("max_branch_summary_length", self.DEFAULT_MAX_LENGTH)

    def enabled(self):
        """Shortening is switched off by blanking the model in the config."""
        return bool(self.model)

    def shorten(self, summary):
        """Return a shortened version of summary, or summary unchanged if it's
        already short enough or Claude can't help.

        The result is plain text with spaces between the words, the same shape
        as the title that went in, so callers sanitise it exactly as they would
        have sanitised the original."""
        if not self.enabled() or len(summary) <= self.max_length:
            return summary

        fragment = self._ask_claude(summary)
        if fragment is None:
            return summary
        return fragment.replace("-", " ")

    def _ask_claude(self, summary):
        if shutil.which("claude") is None:
            return None
        try:
            result = subprocess.run(
                ["claude", "-p", "--model", self.model, "--strict-mcp-config",
                 self.PROMPT.format(summary=summary)],
                capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)
        except (subprocess.SubprocessError, OSError):
            return None
        if result.returncode != 0:
            return None
        return self._validate(result.stdout)

    def _validate(self, reply):
        """Accept only a single line that already looks like a branch fragment
        and is genuinely shorter than what we started with."""
        fragment = reply.strip().strip('`"\'').strip().lower()
        if "\n" in fragment or not self.FRAGMENT_RE.match(fragment):
            return None
        if len(fragment) > self.max_length:
            return None
        return fragment
