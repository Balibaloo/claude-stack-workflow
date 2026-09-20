"""UserPromptSubmit hook: inject the session id, a context estimate, and any
hand-off that waits for a session.

The harness sends a JSON object on stdin with session_id and
transcript_path. The hook prints one line of additional context: the
short session id and the tokens in the context window.

It is a count and not an estimate wherever the transcript allows one.
Every assistant turn records its own usage, and the prompt it was given
is the fresh tokens plus the tokens written to cache plus the tokens read
from cache. The hook reads the last of those. No factor, nothing to
calibrate, and a compaction needs no special case, because the turn after
one is given a smaller prompt and says so.

The byte estimate remains as the fallback, for a transcript that carries
no usage. Its factor was 0.6 and is 0.65, measured on 2026-09-20 against
a 4.7 MB transcript whose last turn reported 771,959 tokens. The old
value read 8 percent low. Reading low is the dangerous direction, because
the hand-off refuses to give a frame to a session at or past 300k, and a
session under-reported as 295k is really near 320k. CONTEXT_FACTOR still
overrides it.

When the hook speaks: on the first prompt of a session, so the wake
message can report the count, and on every prompt from 200k upward.
Below 200k after the wake it prints nothing. Set CONTEXT_ALWAYS=1 to
print on every prompt.

The thresholds come from the brief: 200k is the first warning, 300k is
fine, 400k is the hand-off.

A compaction is found by parsing each line as JSON and reading its
fields. Matching raw text is wrong: any message that quotes the marker
would reset the count.

The hook also reads `.handover/waiting/`. A hand-off that found no
standby waits there, and `tools/handover.py` gives it to the next session
that arms a watcher. A session that starts for other work arms nothing,
and it would walk past the orphaned frame. So the notice rides on the
prompt that every session sends, and it speaks at any context count.
"""

import json
import os
import sys
import time

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


def used(entry):
    """The context an assistant turn actually consumed, from the harness.

    Every assistant turn records its own usage, and the prompt it was
    given is the sum of the fresh tokens, the tokens written to cache and
    the tokens read from cache. That is the number the harness itself
    counted, so reading it beats scaling the transcript's bytes by a
    constant that nobody has measured lately.
    """
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return None
    usage = (entry.get("message") or {}).get("usage")
    if not isinstance(usage, dict):
        return None
    total = 0
    for key in ("input_tokens", "cache_creation_input_tokens",
                "cache_read_input_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)):
            total += value
    return total or None


def scan(path):
    """Return (thousands of tokens, assistant turns) or None.

    The count is the last turn's own usage where the transcript records
    one. A compaction needs no special case there, because the turn after
    it is given a smaller prompt and says so.

    The byte estimate is the fallback, for a transcript that carries no
    usage. Its factor was 0.6 and is 0.65, measured on 2026-09-20 against
    a 4.7 MB transcript whose last turn reported 771,959 tokens: the old
    value read 8 percent low, and reading low is the dangerous direction
    for a ceiling that decides whether a session can finish a frame.
    """
    if not path or not os.path.exists(path):
        return None
    factor = float(os.environ.get("CONTEXT_FACTOR", "0.65"))
    total = 0
    turns = 0
    exact = None
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
                    seen = used(entry)
                    if seen:
                        exact = seen
                total += len(line)
    except OSError:
        return None
    if exact:
        return round(exact / 1000), turns
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


def repo_root(start):
    """The repository that holds the mailbox, from any directory in it.

    A session runs in a subdirectory, and the diff review runs in a
    worktree. Both must find the one mailbox. A worktree's `.git` is a
    file that points into `<checkout>/.git/worktrees/<name>`, so the
    checkout is two levels above that. No subprocess runs here, because
    this code runs on every prompt.
    """
    here = os.path.abspath(start or os.getcwd())
    for _ in range(64):
        dot = os.path.join(here, ".git")
        if os.path.isdir(dot):
            return here
        if os.path.isfile(dot):
            try:
                with open(dot, encoding="utf-8") as handle:
                    text = handle.read().strip()
            except OSError:
                return here
            if text.startswith("gitdir:"):
                gitdir = text.split(":", 1)[1].strip()
                if not os.path.isabs(gitdir):
                    gitdir = os.path.join(here, gitdir)
                parts = os.path.normpath(gitdir).split(os.sep)
                if "worktrees" in parts:
                    common = os.sep.join(parts[:parts.index("worktrees")])
                    return os.path.dirname(common)
            return here
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return os.path.abspath(start or os.getcwd())


def enrol(root, sid, est, turns):
    """Record that this session exists, so a hand-off can reach it later.

    A session that arms no watcher is still reachable by a message, and
    the Principal's habit of opening a window and pasting into it is
    enough to enrol one. The file also carries the context estimate, so
    `tools/handover.py peers` can show which standby is the cleanest. The
    write costs one small file per prompt and fails silent.
    """
    if not sid:
        return
    box = os.path.join(root, ".handover", "sessions")
    try:
        os.makedirs(box, exist_ok=True)
        payload = {
            "sid": sid, "name": peer_name(sid), "cwd": root,
            "est": est, "turns": turns, "t": time.time(),
            "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        target = os.path.join(box, sid + ".json")
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=1)
        os.replace(tmp, target)
    except (OSError, ValueError, TypeError):
        pass


def peer_name(sid):
    """This session's current peer name, read from the harness registry.

    The registry keys a session by its process id and carries the full
    session id, so the eight characters the hook prints can be joined to
    the name a person sees in a peer list. A name is recycled between
    sessions, so it is recorded for a person to read and never used as an
    address. An empty string is the honest answer when the registry moves.
    """
    folder = os.path.join(os.path.expanduser("~"), ".claude", "sessions")
    try:
        names = [n for n in os.listdir(folder) if n.endswith(".json")]
    except OSError:
        return ""
    for name in names:
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                row = json.load(handle)
        except (OSError, ValueError):
            continue
        if str(row.get("sessionId", ""))[:8] == sid:
            return str(row.get("name", ""))
    return ""


def waiting(root):
    """One sentence when a hand-off waits for no session in particular.

    A hand-off that found an empty reserve waits on disk. Any session can
    take it, so every session must hear about it. The hook fails silent:
    a missing directory, a half-written file or a wrong root prints
    nothing, because a broken notice must never break a prompt.
    """
    box = os.path.join(root, ".handover", "waiting")
    lines = []
    try:
        names = sorted(n for n in os.listdir(box) if n.endswith(".json"))
    except OSError:
        return ""
    for name in names:
        try:
            with open(os.path.join(box, name), encoding="utf-8") as handle:
                posted = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(posted, dict):
            # A file that parses to a list or a string would raise on .get,
            # and an exception here breaks the prompt of every session.
            continue
        age = ""
        try:
            hours = (time.time() - float(posted.get("t", 0))) / 3600.0
            if hours >= 1:
                age = ", waiting %.0f hours" % hours
        except (TypeError, ValueError):
            pass
        lines.append("frame {} at commit {}, posted {}{}".format(
            posted.get("frame"), posted.get("commit"), posted.get("iso"), age))
    if not lines:
        return ""
    return (" A hand-off waits for a session: " + "; ".join(lines)
            + ". Take it with the take command before you take new work. If the"
            + " Principal has ruled that frame dead, cancel it with the drop"
            + " command, because this notice repeats until one of those happens.")


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
    root = repo_root(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR"))
    enrol(root, sid, est, turns)
    orphan = waiting(root)
    if not always and not wake and not orphan and est is not None and est < WARN:
        return
    if est is None:
        text = f"Session {sid}. Context estimate unavailable."
    else:
        text = f"Session {sid}. Context estimate {est}k tokens: {level(est)}."
    text += orphan
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }))


if __name__ == "__main__":
    main()
