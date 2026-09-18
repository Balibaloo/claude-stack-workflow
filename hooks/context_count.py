"""UserPromptSubmit hook: inject the session id and a context estimate.

The harness sends a JSON object on stdin with session_id and
transcript_path. The hook prints one line of additional context:
the short session id and an estimate of the tokens in the context
window. The estimate is the transcript bytes since the last compaction,
scaled by CONTEXT_FACTOR and divided by four. The Principal compares the
estimate with the count in the UI and tunes CONTEXT_FACTOR in the
environment. A first calibration gave 0.6: a 1.6 MB transcript against
about 250k in the UI. That factor is calibrated on transcript style, not
on one repository, so it should travel. Check it once and tune it.

When the hook speaks: on the first prompt of a session, so the wake
message can report the count, and on every prompt from 200k upward.
Below 200k after the wake it prints nothing. Set CONTEXT_ALWAYS=1 to
print on every prompt.

The thresholds come from the brief: 200k is the first warning, 300k is
fine, 400k is the hand-off.

A compaction is found by parsing each line as JSON and reading its
fields. Matching raw text is wrong: any message that quotes the marker
would reset the count.
"""

import json
import os
import sys

COMPACT_PREFIX = "This session is being continued from a previous conversation"
WARN = 200


def is_compaction(entry):
    """Return True when the transcript entry marks a compaction."""
    if not isinstance(entry, dict):
        return False
    if entry.get("type") == "summary":
        return True
    if entry.get("isCompactSummary") is True:
        return True
    if entry.get("subtype") == "compact_boundary":
        return True
    message = entry.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.startswith(COMPACT_PREFIX):
            return True
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text", "")
                    if isinstance(text, str) and text.startswith(COMPACT_PREFIX):
                        return True
    return False


def scan(path):
    """Return (estimate in thousands of tokens, assistant turns) or None."""
    if not path or not os.path.exists(path):
        return None
    factor = float(os.environ.get("CONTEXT_FACTOR", "0.6"))
    total = 0
    turns = 0
    try:
        with open(path, "rb") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    entry = None
                if is_compaction(entry):
                    total = 0
                if isinstance(entry, dict) and entry.get("type") == "assistant":
                    turns += 1
                total += len(line)
    except OSError:
        return None
    return round(total * factor / 4 / 1000), turns


def level(est):
    """Return the threshold label for an estimate."""
    if est >= 400:
        return "hand off now"
    if est >= 300:
        return "finish the frame, take no new work"
    if est >= WARN:
        return "first warning"
    return "fine"


def main():
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return
    sid = str(data.get("session_id", ""))[:8]
    result = scan(data.get("transcript_path", ""))
    always = os.environ.get("CONTEXT_ALWAYS") == "1"
    if result is None:
        est, turns = None, 0
    else:
        est, turns = result
    wake = turns == 0
    if not always and not wake and est is not None and est < WARN:
        return
    if est is None:
        text = f"Session {sid}. Context estimate unavailable."
    else:
        text = f"Session {sid}. Context estimate {est}k tokens: {level(est)}."
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }))


if __name__ == "__main__":
    main()
