r"""
A hand-off that lands in a session that sits idle.

    python tools/handover.py standby --sid 2555d93f     # in each fresh session
    python tools/handover.py peers                      # who waits in reserve
    python tools/handover.py hand --frame 7 --commit 82f4e9e
    python tools/handover.py take --sid 2555d93f        # the woken standby

A session at 400k gives its whole stack to a fresh peer and stops. That
is what a hand-off is, and it is the only thing it is. It is never a way
to give a task to another session while the sender keeps working: two
sessions on one stack write over each other's records, and the stack
stops answering "where are we". A frame that needs a session while you
are not full is pushed and named to the Principal, who assigns it.

A message is not how it does that, and the reason is not that messages
fail to arrive. They arrive. Across 248 cross-session messages in one machine's
history, none was ever lost, and 57 that landed in sessions idle for more
than five minutes drained in a median of 0.010 seconds. One bridged 35.8
hours of idle in 0.325 seconds.

A message fails at three other things, each one measured in that same
history.

* It cannot be addressed. A peer is addressed by a name, the name is
  recycled between sessions, and one session answered to two names on two
  days. The Principal names a session id, the peer list shows names, and
  nothing joins the two. So a sender once had to broadcast a frame with
  the words "claim it only if your session id is 4286e076".
* It cannot be proved. Four sends to a row that was listed but closed all
  returned `success: true` and were never delivered anywhere. One receiver
  woke in 68 milliseconds after 15.7 hours and answered with a usage-limit
  notice and nothing else. A sender that reads its own success reads
  nothing.
* It is not free for the receiver. A liveness probe asks a standby to
  spend the clean context that made it worth handing to. One standby
  answered a one-line probe and then read the git log and the stack
  unprompted, in the same turn.

So this tool sends a file instead. The file is addressed by session id,
which the Principal uses and the stack records. A standby arms one
background process that blocks on its claim file and writes a heartbeat.
The sender writes the claim. The process exits, and the harness wakes the
standby, because a background task that exits re-invokes its session.
That wake is the most reliable one on this platform: of 1,732 task
notifications in that history, 1,716 started a turn in a session whose
turn had already ended, after idle gaps up to 13.6 hours, and they drained
in 0.01 to 0.12 seconds. Measured here: a file written by an outside
process woke an idle session 6 seconds later, and the waiting cost that
session no tokens.

A message is still a good second route, and `hand` prints the line for
it. Use it only after the file, and only to nudge a session whose watcher
died.

The reserve is the point. The Principal arms many standbys, and one
hand-off consumes exactly one of them. A claim carries one session id and
is created with an exclusive open, so the other standbys never see it,
never wake, and keep the clean context that makes them worth handing to.
A standby that takes a frame leaves the reserve in the same step, so no
session is ever handed two frames. The queue runs oldest first, because a
queue that the Principal cannot predict is a queue they must watch.

The reserve runs dry, and that is the normal end of a long day. A
hand-off that finds nobody does not fail. It waits on disk as a vacancy.
The next session to arm a watcher takes that vacancy inside a second,
before it blocks on anything, so a reserve that refills at nine in the
morning carries the night's frame with it. The sender still writes the
status line and still says the reserve was empty, because a vacancy is a
mailbox entry and the stack is the record.

A claim that nobody reads comes back. A session can wake and fail to act,
and that happened twice in the history above, both times to a usage
limit. So a claim with no receipt returns to the queue as a vacancy after
`--reclaim` seconds, and the frame keeps moving without a person.

Eight hazards are the reason this is a tool and not six commands. Each
one was measured, and six of them can lose a frame:

* A file that is on disk and will not open is not an absent file. A real
  byte-range lock on a claim made a read return nothing in 0.153 seconds,
  and the caller reported that no hand-off waited. The session then took
  other work and the frame stopped moving. On Windows an on-access virus
  scan, a backup agent or a search indexer holds such a lock, and the
  mailbox sits in a working tree that is edited all day. So a read has
  three answers here, and `Unreadable` is one of them.

* `os.kill(pid, 0)` is not a liveness test on Windows. Signal 0 is
  `CTRL_C_EVENT`, so the call sends Ctrl+C to a process group. Against
  seven live sessions here it raised `OSError [WinError 87]`, and against
  a console group leader it would have interrupted the session it asked
  about. Liveness in this tool is a heartbeat file, and no pid is ever
  signalled.
* A send is not a delivery, and a wake is not an answer. So a sender here
  never reads its own write as proof, and never judges silence on a clock
  of its own. The proof is a receipt that only the receiver can create.
* Two senders can reach 400k together. A claim is created with
  `O_CREAT | O_EXCL`, which gave exactly one winner out of twelve racing
  writers here. One standby can never be handed two frames.
* `os.rename` onto an existing file raises on Windows and replaces in
  silence on POSIX. A standby that took a vacancy straight into its own
  claim path would therefore destroy a sender's claim on macOS and Linux
  and keep it on Windows. So a vacancy is moved to a private name first,
  the claim is created exclusively, and the vacancy goes back if the
  claim was already taken.
* `git rev-parse --show-toplevel` answers the worktree, not the
  repository. The brief runs the diff review and the end-to-end run in a
  worktree, so that answer builds a second reserve that no sender can
  see. Measured: `--show-toplevel` gave `/wt` where `--git-common-dir`
  gave `/main/.git`. The root here is the parent of the common directory.
* A wall clock steps. Every deadline in this tool is `time.monotonic`, so
  an NTP correction cannot end a wait early or extend it for an hour. A
  heartbeat is still a wall clock, because two processes have to compare
  it, and a step there makes a standby look stale, which is the safe way
  to be wrong.
* A reader can catch a half-written state file. Every state write goes to
  a temporary file and then through `os.replace`, which is atomic on
  Windows and on POSIX.

Paths are an eighth trap, and this tool cannot fix it for you. The kit
runs commands in Git Bash, and the tool is Python. Python does not
understand `/c/Users/...`. Pass a Windows path, or a path relative to the
repository.

Exit codes, no overlap.

    standby  0 a claim arrived and is printed, 1 the registration was
             removed so this session must not arm again, 3 the wait ran
             out and the session arms again, 2 a usage error, a bad
             session id, a session that already holds a frame, or a
             session past the ceiling, which leaves the reserve.
    peers    0 at least one free standby waits, 1 none does,
             2 a usage error.
    hand     0 a standby took the frame, 4 the claim is posted and the
             receiver never took it, 5 no free standby exists and the
             hand-off now waits as a vacancy, 2 a usage error, an
             ambiguous `--to`, a named peer that cannot take a frame, or a
             mailbox that could not be written.
    take     0 a claim is printed, 1 no claim waits for this session and
             no hand-off waits for anybody, 6 a claim is here and will not
             open, so retry and take no other work, 2 a usage error.
    release  0 the session left the reserve, 1 it was not in the reserve,
             2 a usage error or a claim that will not open.
    drop     0 the vacancy is cancelled, 1 no vacancy names that frame,
             2 a usage error.
    holding  0 the handed column is corrected, 1 the session is not in the
             reserve, 2 a usage error.

Exit 1 never means "something went wrong here". A write that fails and a
file that will not open both return 2 or 6, because a session that reads
1 as "nothing waits for me" would walk past a live frame.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

BOX = ".handover"
BEAT = 20.0
STALE = 90.0
WAIT = 28800.0
CONFIRM = 90.0
RECLAIM = 900.0
GRACE = 25.0
CEILING = 300      # thousands of tokens, the brief's take-no-new-frame line
POLL = 1.0
VERSION = 2


def _now() -> tuple[float, str]:
    """The clock, twice: seconds for a record, a local string for a person."""
    t = time.time()
    return t, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def _git(start: Path, *args: str) -> str:
    """One git question, answered with an empty string when git cannot."""
    try:
        out = subprocess.run(["git", *args], cwd=str(start),
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _root(start: Path) -> Path:
    """The repository, so a worktree shares one reserve with the checkout.

    `--show-toplevel` answers the worktree. The brief sends the diff
    review and the end-to-end run into a worktree, and a worktree with a
    reserve of its own is a reserve no sender can see. `--git-common-dir`
    answers the main repository in both places.
    """
    common = (_git(start, "rev-parse", "--path-format=absolute", "--git-common-dir")
              or _git(start, "rev-parse", "--git-common-dir"))
    if common:
        path = Path(common)
        if not path.is_absolute():
            path = (start / path).resolve()
        if path.name == ".git" and path.parent.is_dir():
            return path.parent
    top = _git(start, "rev-parse", "--show-toplevel")
    return Path(top) if top else start


class Unreadable(OSError):
    """A file that is on disk and will not open or will not parse.

    A locked file is not an absent file. On Windows an on-access virus
    scan, a backup agent or a search indexer holds a byte range, and the
    read raises PermissionError. Measured with a real byte-range lock: a
    claim read returned nothing in 0.153 seconds, the caller called a live
    frame 7 absent, and the brief told that session to continue. The frame
    stopped moving and no line anywhere named it.

    So this is an exception and never a None. A None means absent, and
    absent means the session may take other work. Every caller that can
    live without the file catches this and writes an audit line. Every
    caller that cannot, stops.
    """


def _read_json(path: Path) -> dict | None:
    """Read a small JSON object. None means absent, and nothing else does.

    A writer mid-replace is retried. A file that still will not give a
    JSON object after the retries raises `Unreadable`, because a caller
    that cannot tell absent from unreadable makes the wrong choice every
    time.
    """
    for _ in range(3):
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return None
        except (ValueError, OSError):
            time.sleep(0.05)
            continue
        if isinstance(data, dict):
            return data
        break
    if path.exists():
        raise Unreadable(str(path))
    return None


def _write_json(target: Path, payload: dict) -> None:
    """Replace a file in one step, so no reader ever sees half of it."""
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
        os.replace(tmp, target)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


@dataclass
class Box:
    """The mailbox on disk. A doorbell, and never a record.

    The record of a hand-off is the status line in the stack, and the
    stack is committed. This directory is machine state, so `.gitignore`
    holds it.
    """

    root: Path
    peers: Path = field(init=False)
    claims: Path = field(init=False)
    waiting: Path = field(init=False)
    taken: Path = field(init=False)
    sessions: Path = field(init=False)
    log: Path = field(init=False)
    unreadable: list = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        box = self.root / BOX
        self.peers = box / "peers"
        self.claims = box / "claims"
        self.waiting = box / "waiting"
        self.taken = box / "taken"
        self.sessions = box / "sessions"
        self.log = box / "log.jsonl"
        for d in (self.peers, self.claims, self.waiting, self.taken, self.sessions):
            d.mkdir(parents=True, exist_ok=True)

    def peer_file(self, sid: str) -> Path:
        return self.peers / (sid + ".json")

    def claim_file(self, sid: str) -> Path:
        return self.claims / (sid + ".json")

    def note(self, event: str, **fields: object) -> None:
        """Append one audit line. A hand-off that fails must leave a trace."""
        t, iso = _now()
        line = json.dumps({"t": round(t, 3), "iso": iso, "event": event, **fields})
        try:
            with self.log.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    def soft(self, path: Path, where: str) -> dict | None:
        """Read a row this command can do without, and record a file it cannot read.

        A row that will not open is skipped, because one bad file must not
        stop a queue from printing. It is never skipped in silence: the
        name goes on the box's list and `peers` prints it.
        """
        try:
            return _read_json(path)
        except Unreadable:
            if path.name not in self.unreadable:
                self.unreadable.append(path.name)
            self.note("unreadable", file=path.name, where=where)
            return None

    def write_state(self, sid: str, state: dict) -> None:
        _write_json(self.peer_file(sid), state)

    def read_state(self, sid: str) -> dict | None:
        return self.soft(self.peer_file(sid), "peer state")

    def enrolled(self, sid: str) -> dict | None:
        """What the context hook last recorded about a session.

        The hook runs on every prompt, so the Principal's habit of opening
        a window and pasting into it enrols that session at no cost. An
        enrolled session with no watcher is still reachable by a message.
        """
        return self.soft(self.sessions / (sid + ".json"), "enrolment")

    def vacancies(self) -> list[dict]:
        """Hand-offs that found no standby, oldest first.

        A drought does not cancel a hand-off. It turns the hand-off into a
        vacancy that waits on disk for the next session to arm.
        """
        out = []
        for path in sorted(self.waiting.glob("*.json")):
            posted = self.soft(path, "vacancy")
            if posted:
                posted["file"] = path.name
                out.append(posted)
        out.sort(key=lambda p: float(p.get("t", 0)))
        return out

    def queue(self, stale: float, ceiling: float = CEILING) -> list[dict]:
        """Every peer, oldest first, each row carrying its heartbeat age.

        A peer with a claim it has not taken is `woken`, and it is not
        free. Its watcher has already exited, so its heartbeat stops, and
        a row that read only the heartbeat would call it stale or, worse,
        free. The reserve must never offer one standby twice.
        """
        out = []
        now = time.time()
        for path in sorted(self.peers.glob("*.json")):
            state = self.soft(path, "peer state")
            if not state:
                continue
            sid = str(state.get("sid", ""))
            state["age"] = round(now - float(state.get("beat", 0)), 1)
            # A heartbeat from the future is never live. Two machines on one
            # shared checkout, or a clock that stepped, would otherwise give
            # a dead session an age below zero and keep it free for ever.
            state["live"] = -stale <= state["age"] <= stale
            state["ahead"] = state["age"] < -1.0
            state["claimed"] = self.claim_file(sid).exists()
            # Read the enrolment before anything derived from it. The
            # ceiling below is computed from `est`, and an earlier version
            # of this loop read `est` one line too soon, so every row was
            # eligible however full it was.
            enrolled = self.enrolled(sid) or {}
            state["est"] = enrolled.get("est")
            # The hook reads the name from the harness registry. A session
            # cannot know its own peer name without asking for a peer list,
            # so a name typed at arm time is a guess, and a wrong name is
            # unaddressable on the one route that needs it. The hook wins.
            state["name"] = enrolled.get("name") or state.get("name") or ""
            # A session at the brief's 300k line must take no new frame, so
            # it must not be handed one either. An unknown estimate is the
            # normal state of the cleanest standby there is: a window armed
            # on its first prompt has no transcript to measure yet, and it
            # stays unmeasured for as long as it sits quiet. So unknown is
            # eligible, and it is not a risk, it is a new window.
            est = state["est"]
            state["over"] = isinstance(est, (int, float)) and est >= ceiling
            state["free"] = (state["live"] and not state["claimed"]
                             and state.get("state") == "standby"
                             and not state["over"])
            out.append(state)
        out.sort(key=lambda s: float(s.get("since", 0)))
        return out

    def reclaim(self, older_than: float) -> list[dict]:
        """Return every unread claim to the queue as a vacancy.

        A session can wake and fail to act. It happened twice in the
        history this tool was built from, both times to a usage limit. A
        claim with no receipt is therefore not a frame that is moving, and
        after a while it must move again.
        """
        if older_than <= 0:
            return []
        back = []
        now = time.time()
        for path in sorted(self.claims.glob("*.json")):
            claim = self.soft(path, "claim")
            if not claim:
                continue
            if now - float(claim.get("t", now)) < older_than:
                continue
            sid = path.stem
            state = self.read_state(sid) or {}
            if state.get("state") == "holding":
                continue
            staging = self.claims / (path.name + ".reclaiming")
            try:
                os.rename(str(path), str(staging))
            except OSError:
                continue
            claim["reclaimed_from"] = sid
            self._post(claim)
            try:
                os.unlink(staging)
            except OSError:
                pass
            # The watcher that was blocking when this claim arrived saw it
            # and exited, so that registration is waiting for nothing and a
            # sender must not be offered it. But a session that timed out,
            # re-armed, and is blocking again owns a NEWER registration, and
            # that one is alive. Evicting it would tell a healthy standby to
            # leave the reserve and never come back. So the registration
            # goes only when it predates the claim.
            armed_at = float(state.get("armed_at", 0) or 0)
            if armed_at <= float(claim.get("t", 0)):
                try:
                    self.peer_file(sid).unlink()
                except FileNotFoundError:
                    pass
            else:
                self.note("reclaim_kept_newer_watcher", sid=sid,
                          armed_at=armed_at, claim_t=claim.get("t"))
            self.note("reclaimed", sid=sid, frame=claim.get("frame"),
                      after=round(now - float(claim.get("t", now))))
            back.append(claim)
        return back

    def _post(self, payload: dict) -> Path:
        """Write a vacancy under a name that collides with no other."""
        safe = "".join(c for c in str(payload.get("frame", ""))
                       if c.isalnum() or c in "-_.") or "unnamed"
        stamp = str(payload.get("t", time.time())).replace(".", "")[-9:]
        target = self.waiting / ("frame-%s-%s.json" % (safe, stamp))
        n = 0
        while target.exists():
            n += 1
            target = self.waiting / ("frame-%s-%s-%d.json" % (safe, stamp, n))
        payload.pop("file", None)
        _write_json(target, payload)
        return target


def _post_vacancy(box: Box, args: argparse.Namespace) -> int:
    """Leave the hand-off on disk for the next session, and say so loudly.

    A drought is the normal end of a long day: the reserve empties and the
    Principal is away. The frame must not depend on them noticing. The
    vacancy waits, the next standby to arm takes it within a second, and
    the status line still carries the fact for a person to read.
    """
    t, iso = _now()
    target = box._post({
        "frame": args.frame, "commit": args.commit,
        "from_sid": args.sender or "", "note": args.note or "",
        "t": t, "iso": iso, "host": socket.gethostname(), "tool": VERSION,
    })
    box.note("vacancy_posted", frame=args.frame, commit=args.commit,
             file=target.name)
    print("NO FREE STANDBY. The hand-off waits in %s as a vacancy." % target)
    print("The next session that arms a watcher takes frame %s within a second."
          % args.frame)
    print("Write the status line now: frame %s is handed to nobody yet, commit %s."
          % (args.frame, args.commit))
    print("Then commit the stack and stop. Tell the Principal the reserve is empty.")
    unarmed = _unarmed(box)
    if unarmed:
        print("These sessions sent a prompt but arm no watcher, newest first:")
        for row in unarmed[:5]:
            print("  %s  %s  last prompt %s" % (
                row.get("sid"), row.get("name") or "-", row.get("iso")))
        print("A message to one of them still lands. Tell it to run:")
        print("  tools/handover.py take --sid <its session id>")
        print("It must take the vacancy itself, because no claim names it yet.")
    return 5


def _wake_from_sleep(box: Box, stale: float, grace: float,
                     ceiling: float = CEILING) -> list[dict]:
    """The queue, after a moment's grace for a machine that just woke up.

    A closed laptop lid stops every heartbeat at once. The watchers are
    alive and they beat again within one interval, but a sender that reads
    the queue in that moment sees a reserve of stale rows and declares a
    drought. It would then post a vacancy while six standbys sit ready.

    So when rows exist and none is free, and the stale ones all fell
    silent at about the same time, wait one beat and read again. A truly
    dead reserve costs this delay once.
    """
    rows = box.queue(stale, ceiling)
    if grace <= 0 or not rows or any(r["free"] for r in rows):
        return rows
    ages = [r["age"] for r in rows if not r["live"] and not r.get("ahead")]
    if len(ages) < 1 or (max(ages) - min(ages)) > BEAT * 2:
        return rows
    print("every standby fell silent together, %.0fs ago. Waiting one beat, in"
          % min(ages))
    print("case this machine just woke up.")
    sys.stdout.flush()
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        time.sleep(POLL)
        fresh = box.queue(stale, ceiling)
        if any(r["free"] for r in fresh):
            print("the reserve came back.")
            return fresh
    print("no heartbeat came back, so the reserve is genuinely gone.")
    return box.queue(stale, ceiling)


def _unarmed(box: Box) -> list[dict]:
    """Sessions the hook enrolled that hold no live watcher, newest first."""
    rows = []
    armed = {str(r.get("sid")) for r in box.queue(STALE) if r["live"]}
    for path in box.sessions.glob("*.json"):
        row = box.soft(path, "enrolment")
        if not row:
            continue
        if str(row.get("sid")) in armed:
            continue
        rows.append(row)
    rows.sort(key=lambda r: float(r.get("t", 0)), reverse=True)
    return rows


def _consume_vacancy(box: Box, sid: str) -> dict | None:
    """Take the oldest hand-off that waited through the drought, if one waits.

    Two renames, and never one. The first moves the vacancy to a private
    name, so exactly one arming session owns it. The second is an
    exclusive create of this session's claim, which fails when a sender
    claimed this session in the same moment. The vacancy then goes back,
    because a frame that vanishes into a race is the one thing this tool
    must never do.
    """
    if box.claim_file(sid).exists():
        return None
    for posted in box.vacancies():
        source = box.waiting / str(posted["file"])
        staging = box.waiting / ("%s.taking-%s" % (posted["file"], sid))
        try:
            os.rename(str(source), str(staging))
        except OSError:
            continue
        payload = {k: v for k, v in posted.items() if k != "file"}
        try:
            fd = os.open(str(box.claim_file(sid)),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            box._post(payload)
            try:
                os.unlink(staging)
            except OSError:
                pass
            box.note("vacancy_returned", sid=sid, frame=payload.get("frame"))
            return None
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
        try:
            os.unlink(staging)
        except OSError:
            pass
        box.note("vacancy_filled", sid=sid, frame=payload.get("frame"))
        return payload
    return None


def cmd_standby(args: argparse.Namespace, box: Box) -> int:
    """Register, then block until a claim arrives. The model spends nothing here."""
    # A session past the brief's 300k line takes no new frame, so a seat it
    # holds is a seat no hand-off can ever use. It leaves instead of arming,
    # and says so, rather than making the reserve look larger than it is.
    enrolled = box.enrolled(args.sid) or {}
    est = enrolled.get("est")
    if isinstance(est, (int, float)) and est >= args.ceiling:
        box.note("arm_refused_over_ceiling", sid=args.sid, est=est)
        for path in (box.peer_file(args.sid), box.claim_file(args.sid)):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        print("this session reads %sk, at or past the %.0fk ceiling." % (
            est, args.ceiling))
        print("A session there takes no new frame, so it is handed none, and a")
        print("seat it holds is a seat nothing can use. It has left the reserve.")
        print("Tell the Principal a window is needed, and do not arm again.")
        return 2

    old = box.read_state(args.sid)
    if old and old.get("state") == "holding":
        print("%s holds frame %s already." % (args.sid, old.get("frame")))
        print("A session that holds a frame is not a standby. It cannot be")
        print("handed a second one. Run release first, and only if the frame")
        print("is closed or was given to somebody else.")
        return 2

    t, iso = _now()
    state = {
        "sid": args.sid,
        "name": args.name or "",
        "host": socket.gethostname(),
        "watcher_pid": os.getpid(),
        "since": t,
        "since_iso": iso,
        # `since` keeps the queue order across a re-arm. `armed_at` is this
        # watcher's own start, and it decides two things a heartbeat cannot:
        # which of two watchers for one session is the newer, and whether a
        # registration predates the claim a reclaim is giving back.
        "armed_at": t,
        "beat": t,
        "state": "standby",
        "frame": None,
        "tool": VERSION,
    }
    if old and old.get("since"):
        state["since"] = old["since"]
        state["since_iso"] = old.get("since_iso", iso)
    box.write_state(args.sid, state)
    box.note("armed", sid=args.sid, name=state["name"], wait=args.wait)
    print("standby %s armed at %s, blocking up to %.0fs" % (args.sid, iso, args.wait))

    took = _consume_vacancy(box, args.sid)
    if took:
        print("a hand-off was already waiting, posted %s, so this standby takes it"
              % took.get("iso", "earlier"))
    sys.stdout.flush()

    start = time.monotonic()
    last_beat = start
    said = False
    while time.monotonic() - start < args.wait:
        try:
            claim = _read_json(box.claim_file(args.sid))
        except Unreadable:
            claim = None
            if not said:
                said = True
                box.note("claim_unreadable", sid=args.sid, where="watcher")
                print("a claim is here and will not open. Something holds the file.")
                print("Still blocking, and retrying every second.")
                sys.stdout.flush()
        if claim:
            _, found = _now()
            box.note("woken", sid=args.sid, frame=claim.get("frame"))
            print("CLAIM at %s, after %.0fs of blocking" % (
                found, time.monotonic() - start))
            print(json.dumps(claim, indent=1))
            print("Now run: python tools/handover.py take --sid %s" % args.sid)
            return 0
        if not box.peer_file(args.sid).exists():
            box.note("watcher_released", sid=args.sid)
            print("the registration is gone, so this session left the reserve.")
            print("Do not arm the watcher again. Ask the Principal for work.")
            return 1
        if time.monotonic() - last_beat >= args.beat:
            last_beat = time.monotonic()
            # Read before writing, so the beat updates one field and never
            # restores this watcher's own view of the rest. That is what
            # lets a newer watcher be seen here at all.
            current = box.read_state(args.sid)
            if current and float(current.get("armed_at", 0) or 0) > state["armed_at"]:
                box.note("watcher_retired", sid=args.sid,
                         mine=state["armed_at"], newer=current.get("armed_at"))
                print("a newer watcher arms this session, so this one stops.")
                print("One session, one watcher. Do not arm again from here.")
                return 1
            merged = current or state
            merged["beat"] = time.time()
            try:
                box.write_state(args.sid, merged)
            except OSError:
                pass
            # A vacancy can appear while this standby is already waiting,
            # because a reclaim gives an unread claim back to the queue.
            # A watcher that only ever watched its own claim file would
            # block for hours beside a frame that needs a session.
            if _consume_vacancy(box, args.sid):
                print("a hand-off was waiting for any session, so this standby")
                print("took it while it was blocked.")
                sys.stdout.flush()
        time.sleep(POLL)
    box.note("wait_ran_out", sid=args.sid, seconds=args.wait)
    print("no claim in %.0fs. Arm the watcher again, then stop." % args.wait)
    return 3


def _print_queue(rows: list[dict], stale: float) -> int:
    """Print the reserve and return how many standbys are free to take a frame."""
    print("%-10s %-22s %-9s %-7s %-6s %-6s %s" % (
        "sid", "name", "state", "beat", "handed", "ctx", "armed"))
    free = 0
    for r in rows:
        beat = "%.0fs" % r["age"] if r["live"] else "STALE"
        if r.get("ahead"):
            beat = "AHEAD"
        shown = r.get("state", "?")
        if r["claimed"] and shown == "standby":
            shown = "woken"
        if shown == "holding" and r.get("frame") is None:
            # It held a frame, holds none now, and nothing is watching for
            # it. That is not a standby and it is not a holder.
            shown = "spent"
            beat = "-"
        elif shown == "holding":
            # A holder's watcher exited when it delivered the claim, so the
            # beat stops by design. Printing STALE there says a working
            # session died.
            beat = "held"
        if r.get("over") and shown == "standby":
            shown = "full"
        if r["free"]:
            free += 1
        est = r.get("est")
        print("%-10s %-22s %-9s %-7s %-6s %-6s %s" % (
            r.get("sid", "?"), (r.get("name") or "-")[:22], shown, beat,
            r.get("frame") if r.get("frame") is not None else "-",
            ("%dk" % est) if isinstance(est, int) else "-",
            r.get("since_iso", "?")))
    print("%d free standby, %d row(s). A heartbeat older than %.0fs is stale." % (
        free, len(rows), stale))
    print("free means live, armed, and not already claimed by another sender.")
    print("full means it is armed and at or past the ceiling, so no frame")
    print("goes to it. It leaves the reserve when its wait next runs out.")
    print("spent means it held a frame, holds none now, and no watcher runs.")
    print("A spent session arms again to rejoin the reserve, or releases.")
    print("handed is the frame this mailbox delivered, and not the frame a")
    print("session holds now. The stack is the record of that. A session that")
    print("moved on corrects the column with the holding command.")
    return free


def cmd_peers(args: argparse.Namespace, box: Box) -> int:
    """Print the reserve. This replaces the liveness probe the brief used to send."""
    for claim in box.reclaim(args.reclaim):
        print("RECLAIMED: frame %s went back to the queue, unread." % claim.get("frame"))
    rows = box.queue(args.stale, args.ceiling)
    free = 0
    if not rows:
        print("no peer has armed a watcher in %s" % (box.root / BOX))
    else:
        free = _print_queue(rows, args.stale)
    for v in box.vacancies():
        print("WAITING: frame %s, commit %s, posted %s by %s" % (
            v.get("frame"), v.get("commit"), v.get("iso"),
            v.get("from_sid") or "an unnamed session"))
    unarmed = _unarmed(box)
    if unarmed:
        print("%d session(s) sent a prompt and arm no watcher: %s" % (
            len(unarmed), ", ".join(str(r.get("sid")) for r in unarmed[:6])))
        print("A message reaches those. A claim file does not wake them.")
    for name in box.unreadable:
        print("UNREADABLE: %s is on disk and will not open, so it was skipped."
              % name)
    if box.unreadable:
        print("A claim in that state cannot go back to the queue. Find what holds")
        print("the file, or move it aside by hand, and run this again.")
    return 0 if free else 1


def cmd_hand(args: argparse.Namespace, box: Box) -> int:
    """Give the frame to one standby, then wait for the fact that proves it landed."""
    box.reclaim(args.reclaim)
    rows = _wake_from_sleep(box, args.stale, args.grace, args.ceiling)
    if args.to:
        wanted = [r for r in rows if str(r.get("sid", "")).startswith(args.to)]
        if len(wanted) > 1:
            print("--to %s names %d sessions: %s" % (
                args.to, len(wanted),
                ", ".join(str(r.get("sid")) for r in wanted)))
            print("Give more characters of the session id. Nothing was handed off.")
            return 2
        if not wanted:
            # The Principal named a session. Substituting another one, or
            # turning the frame into a vacancy for anybody, would answer a
            # different question than the one they asked.
            free = [str(r.get("sid")) for r in rows if r["free"]]
            print("--to %s names no session in the reserve." % args.to)
            print("Free standbys now: %s" % (", ".join(free) if free else "none"))
            print("Nothing was handed off. Check the id, or drop --to.")
            return 2
        if not wanted[0]["free"]:
            row = wanted[0]
            if row.get("frame"):
                why = "it holds frame %s" % row.get("frame")
            elif row.get("claimed"):
                why = "a claim already waits for it"
            elif row.get("over"):
                why = ("it reads %sk, at or past the %.0fk ceiling"
                       % (row.get("est"), args.ceiling))
            else:
                why = "its last heartbeat was %.0fs ago" % row["age"]
            print("%s cannot take a frame: %s." % (row.get("sid"), why))
            free = [str(r.get("sid")) for r in rows if r["free"]]
            print("Free standbys now: %s" % (", ".join(free) if free else "none"))
            print("Nothing was handed off. Name another session, or drop --to.")
            return 2
    else:
        wanted = [r for r in rows if r["free"]]
    if not wanted:
        blocked = [r for r in rows if r["live"] and r.get("over")
                   and r.get("state") == "standby"]
        if blocked:
            print("%d standby is over the %.0fk ceiling and cannot take a frame:"
                  % (len(blocked), args.ceiling))
            for r in blocked:
                print("  %s at %sk" % (r.get("sid"), r.get("est")))
            print("A session at the brief's 300k line takes no new frame, so it")
            print("is handed none. This is a drought, and not an empty reserve.")
        box.note("no_standby", frame=args.frame, commit=args.commit,
                 over_ceiling=len(blocked))
        return _post_vacancy(box, args)

    taken = None
    for row in wanted:
        sid = str(row["sid"])
        if not row["live"]:
            print("skip %s: last heartbeat %.0fs ago" % (sid, row["age"]))
            continue
        if row.get("state") != "standby":
            print("skip %s: it holds frame %s" % (sid, row.get("frame")))
            continue
        if row.get("claimed"):
            print("skip %s: a claim already waits for it" % sid)
            continue
        t, iso = _now()
        claim = {
            "frame": args.frame, "commit": args.commit,
            "from_sid": args.sender or "", "note": args.note or "",
            "t": t, "iso": iso, "host": socket.gethostname(), "tool": VERSION,
        }
        try:
            fd = os.open(str(box.claim_file(sid)),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            print("skip %s: another sender claimed it first" % sid)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(claim, fh, indent=1)
        box.note("claim_posted", sid=sid, frame=args.frame, commit=args.commit)
        print("claim for frame %s posted to %s at %s" % (args.frame, sid, iso))
        taken = sid
        break
    if taken is None:
        box.note("all_skipped", frame=args.frame, commit=args.commit)
        print("every standby above was taken or stale.")
        return _post_vacancy(box, args)

    start = time.monotonic()
    while time.monotonic() - start < args.confirm:
        state = box.read_state(taken)
        if (state and state.get("state") == "holding"
                and str(state.get("frame")) == str(args.frame)):
            box.note("confirmed", sid=taken, frame=args.frame)
            print("CONFIRMED: %s holds frame %s, %.0fs after the claim." % (
                taken, args.frame, time.monotonic() - start))
            print("Write the status line with %s as the holder, commit, and stop."
                  % taken)
            print("Stop means stop. The stack is theirs now, and two sessions on")
            print("one stack write over each other.")
            return 0
        time.sleep(POLL)
    box.note("unconfirmed", sid=taken, frame=args.frame, seconds=args.confirm)
    print("UNCONFIRMED after %.0fs. %s holds the claim and has not taken it." % (
        args.confirm, taken))
    name = (box.read_state(taken) or {}).get("name") or ""
    if name:
        print("Second route, once only: message the peer named %s and say" % name)
        print("  run: tools/handover.py take --sid %s" % taken)
        print("That name was true when the watcher armed. A name is recycled, so")
        print("check the reply names session %s before you believe it." % taken)
    print("The claim returns to the queue by itself in %.0f minutes." % (
        args.reclaim / 60.0))
    print("Say so in the status line, name %s, commit the stack, and stop." % taken)
    return 4


def cmd_take(args: argparse.Namespace, box: Box) -> int:
    """Read the claim and consume it, so the take is a fact and not a reading.

    The claim moves into `taken/` before anything else. That move is the
    receipt: it cannot be done twice, and it stops a reclaim from handing
    this frame to somebody else while this session works on it.
    """
    source = box.claim_file(args.sid)
    try:
        claim = _read_json(source)
    except Unreadable:
        box.note("claim_unreadable", sid=args.sid, where="take")
        print("the claim for %s is here and will not open." % args.sid)
        print("Something holds the file: a scan, a backup agent, an indexer.")
        print("Run take again in a minute. Do not take other work, and do not")
        print("report that no hand-off waits. A frame is addressed to you.")
        return 6
    if not claim:
        took = _consume_vacancy(box, args.sid)
        if took:
            claim = _read_json(source)
            print("no claim named you, and a hand-off was waiting for any session.")
        else:
            print("no claim for %s, and no hand-off waits." % args.sid)
            print("Arm the watcher again, or ask the Principal for work.")
            return 1
    t, iso = _now()
    safe = "".join(c for c in str(claim.get("frame", "")) if c.isalnum() or c in "-_.")
    receipt = box.taken / ("%s-frame-%s.json" % (args.sid, safe or "unnamed"))
    n = 0
    while receipt.exists():
        n += 1
        receipt = box.taken / ("%s-frame-%s-%d.json" % (args.sid, safe or "x", n))
    try:
        os.rename(str(source), str(receipt))
    except OSError:
        print("the claim for %s is gone. It was reclaimed or already taken." % args.sid)
        print("Run peers, and ask the Principal for work.")
        return 1

    state = box.read_state(args.sid) or {"sid": args.sid, "since": t,
                                         "since_iso": iso}
    state.update({
        "state": "holding", "frame": claim.get("frame"), "beat": t,
        "took_iso": iso, "from_sid": claim.get("from_sid", ""),
        "receipt": receipt.name, "tool": VERSION,
    })
    box.write_state(args.sid, state)
    box.note("taken", sid=args.sid, frame=claim.get("frame"), receipt=receipt.name)
    print("frame %s, stack commit %s, from %s, posted %s" % (
        claim.get("frame"), claim.get("commit"),
        claim.get("from_sid") or "unknown", claim.get("iso")))
    if claim.get("note"):
        print("note: %s" % claim["note"])
    print("Claim the frame in the stack with your session id, then read the commit.")
    return 0


def cmd_release(args: argparse.Namespace, box: Box) -> int:
    """Leave the reserve. A standby that became a worker is no longer a standby.

    A live watcher writes its heartbeat again a moment after the
    deletion, so one unlink does not evict anything. The command deletes
    until the file stays gone, and the watcher exits when it finds its
    registration missing. The two halves converge inside one poll.
    """
    # A release must never swallow a frame. An unread claim goes back to
    # the queue first, because deleting it would end the hand-off with a
    # line that says success and names nothing.
    held = box.read_state(args.sid) or {}
    if box.claim_file(args.sid).exists() and held.get("state") != "holding":
        try:
            claim = _read_json(box.claim_file(args.sid))
        except Unreadable:
            print("a claim for %s will not open, so nothing was released." % args.sid)
            print("Retry in a minute, or move the file aside by hand.")
            return 2
        if claim:
            claim["reclaimed_from"] = args.sid
            target = box._post(claim)
            box.note("released_claim_back", sid=args.sid, frame=claim.get("frame"),
                     file=target.name)
            print("frame %s was claimed and unread, so it went back to the queue."
                  % claim.get("frame"))

    gone = False
    for path in (box.peer_file(args.sid), box.claim_file(args.sid)):
        try:
            path.unlink()
            gone = True
        except FileNotFoundError:
            pass
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if not box.peer_file(args.sid).exists():
            break
        try:
            box.peer_file(args.sid).unlink()
        except FileNotFoundError:
            pass
        time.sleep(POLL)
    box.note("released", sid=args.sid)
    print("%s left the reserve" % args.sid if gone
          else "%s was not in the reserve" % args.sid)
    return 0 if gone else 1


def cmd_drop(args: argparse.Namespace, box: Box) -> int:
    """Cancel a vacancy the Principal has ruled dead.

    A vacancy is an order, and the hook repeats it at every prompt of
    every session until somebody takes it. A frame that was closed by hand,
    or abandoned, would otherwise be ordered for ever. Only the Principal
    rules a frame dead, so this command exists for them and the receipt
    stays in the log.
    """
    rows = box.vacancies()
    if not rows:
        print("no hand-off waits, so there is nothing to cancel.")
        return 1
    hit = [v for v in rows if str(v.get("frame")) == str(args.frame)]
    if not hit:
        print("no vacancy names frame %s. These wait: %s" % (
            args.frame, ", ".join(str(v.get("frame")) for v in rows)))
        return 1
    for v in hit:
        path = box.waiting / str(v["file"])
        moved = box.taken / ("dropped-frame-%s-%s.json" % (
            "".join(c for c in str(v.get("frame")) if c.isalnum()),
            str(v.get("t", "")).replace(".", "")[-9:]))
        try:
            os.rename(str(path), str(moved))
        except OSError:
            print("could not cancel %s. Run this again." % path.name)
            return 2
        box.note("vacancy_dropped", frame=v.get("frame"), reason=args.reason or "",
                 file=moved.name)
        print("frame %s no longer waits. The record of it is %s." % (
            v.get("frame"), moved.name))
    print("Write in the stack why the frame was cancelled. A vacancy is a")
    print("doorbell, and the stack is the record.")
    return 0


def cmd_holding(args: argparse.Namespace, box: Box) -> int:
    """Say which frame this session holds now, or that it holds none.

    The mailbox records the frame it delivered, and it cannot know what
    happened next. A session took frame 43, closed it, claimed frame 46,
    and its row still read 43 an hour later, so a live row contradicted
    the stack. There was no command for it and the file was edited by
    hand. Machine state that a person has to edit by hand is a defect.
    """
    state = box.read_state(args.sid)
    if not state:
        print("%s is not in the reserve, so there is nothing to correct." % args.sid)
        return 1
    was = state.get("frame")
    if args.frame.lower() in ("none", "-", ""):
        # Do not call it a standby. Its watcher exited when it took the
        # frame, so writing "standby" here produces a row with a dead
        # heartbeat, which the table's own legend reads as a session that
        # died. A session becomes a standby again by arming, and never by
        # saying it holds nothing.
        state["frame"] = None
        state["title"] = ""
    else:
        state["frame"] = args.frame
        state["state"] = "holding"
    box.write_state(args.sid, state)
    box.note("holding_set", sid=args.sid, was=was, now=state["frame"])
    print("%s: handed was %s, and now reads %s." % (
        args.sid, was if was is not None else "-",
        state["frame"] if state["frame"] is not None else "-"))
    if state["frame"] is None:
        print("You hold no frame, and no watcher runs for you. That is not a")
        print("standby. Arm again to rejoin the reserve, or release to leave it.")
    print("The stack is still the record of what you hold. This is the doorbell.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="A hand-off that lands in a session that sits idle.")
    p.add_argument("--root", default=None,
                   help="the repository root, when it is not this directory")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("standby", help="register and block until a claim arrives")
    s.add_argument("--sid", required=True,
                   help="this session id, the eight characters the hook prints")
    s.add_argument("--name", default=None,
                   help="only for a checkout with no context hook. The hook reads "
                        "the true peer name from the harness registry and wins.")
    s.add_argument("--wait", type=float, default=WAIT,
                   help="seconds to block before it asks to be armed again")
    s.add_argument("--beat", type=float, default=BEAT,
                   help="seconds between heartbeats")
    s.add_argument("--ceiling", type=float, default=CEILING,
                   help="thousands of tokens above which this session leaves "
                        "the reserve instead of arming")

    q = sub.add_parser("peers", help="print the reserve of standbys")
    q.add_argument("--stale", type=float, default=STALE,
                   help="seconds of silence that make a heartbeat stale")
    q.add_argument("--reclaim", type=float, default=RECLAIM,
                   help="seconds before an unread claim returns to the queue")
    q.add_argument("--ceiling", type=float, default=CEILING,
                   help="thousands of tokens above which a standby is not free")

    h = sub.add_parser(
        "hand",
        help="give the stack to one live standby and stop working. Not a way "
             "to hand a task to a peer while you keep the seat.")
    h.add_argument("--frame", required=True, help="the frame number")
    h.add_argument("--commit", required=True, help="the stack's commit")
    h.add_argument("--to", default=None,
                   help="a session id prefix, when the Principal names the peer")
    h.add_argument("--sender", default=None,
                   help="the handing session's id, for the record")
    h.add_argument("--note", default=None, help="one line the receiver must read")
    h.add_argument("--stale", type=float, default=STALE)
    h.add_argument("--reclaim", type=float, default=RECLAIM)
    h.add_argument("--ceiling", type=float, default=CEILING,
                   help="thousands of tokens above which a standby is not "
                        "handed a frame, from the brief's 300k line")
    h.add_argument("--grace", type=float, default=GRACE,
                   help="seconds to wait for a heartbeat when every standby fell "
                        "silent together, as a sleeping machine does")
    h.add_argument("--confirm", type=float, default=CONFIRM,
                   help="seconds to wait for the take, under 110 and under 300")

    t = sub.add_parser("take", help="read the claim addressed to this session")
    t.add_argument("--sid", required=True)

    r = sub.add_parser("release", help="leave the reserve")
    r.add_argument("--sid", required=True)

    o = sub.add_parser("holding", help="correct the frame this session holds")
    o.add_argument("--sid", required=True)
    o.add_argument("--frame", required=True,
                   help="the frame held now, or none when the session holds one no longer")

    d = sub.add_parser("drop", help="cancel a hand-off that waits for nobody")
    d.add_argument("--frame", required=True, help="the frame to stop offering")
    d.add_argument("--reason", default=None, help="why, for the log")
    return p


def _check_sid(sid: str) -> str:
    """A session id is an address, so it may not be a path.

    `--sid ../../x` would put a peer file and a claim file outside the
    mailbox, and two ids that differ only by a separator would collapse
    onto one file. The hook prints eight characters of a UUID, so this is
    what an id may hold.
    """
    if not sid or len(sid) > 64:
        return "a session id holds 1 to 64 characters"
    for ch in sid:
        if not (ch.isalnum() or ch in "-_"):
            return "a session id holds letters, digits, dash and underscore only"
    return ""


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for name in ("sid", "to"):
        value = getattr(args, name, None)
        if value:
            bad = _check_sid(value)
            if bad:
                print("--%s is not usable: %s" % (name, bad), file=sys.stderr)
                return 2
    start = Path(args.root) if args.root else Path.cwd()
    if not start.is_dir():
        print("--root is not a directory: %s" % start, file=sys.stderr)
        return 2
    confirm = getattr(args, "confirm", 0.0)
    if confirm and confirm >= 110:
        print("--confirm %.0f is too long. The Bash tool stops a foreground"
              % confirm, file=sys.stderr)
        print("command at 120 seconds by default, and a sender that never reads",
              file=sys.stderr)
        print("its exit code can hand one frame to two sessions. Use 90 or less,",
              file=sys.stderr)
        print("or raise the tool's own timeout first.", file=sys.stderr)
        return 2
    box = Box(_root(start))
    try:
        return {
            "standby": cmd_standby, "peers": cmd_peers, "hand": cmd_hand,
            "take": cmd_take, "release": cmd_release, "drop": cmd_drop,
            "holding": cmd_holding,
        }[args.cmd](args, box)
    except Unreadable as exc:
        print("a file is on disk and will not open: %s" % exc, file=sys.stderr)
        print("Nothing was changed. Find what holds it, then run this again.",
              file=sys.stderr)
        return 2
    except OSError as exc:
        # A write that fails must not leave the exit code lying. Python's own
        # exit 1 means "no claim waits" to a session reading the table above.
        box.note("io_error", cmd=args.cmd, error=str(exc))
        print("the mailbox could not be written: %s" % exc, file=sys.stderr)
        print("Nothing here is proof. Tell the Principal, and do not report a",
              file=sys.stderr)
        print("hand-off as done.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
