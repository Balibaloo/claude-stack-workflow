r"""
The hand-off, tested on the promises a session bets its frame on.

Four promises carry the whole tool, so each one gets a test that fails
loudly when it breaks:

* One claim wakes exactly one standby. The rest of the reserve keeps the
  clean context that made it worth handing to.
* Two senders that hand off in the same second take two different
  standbys. Never the same one.
* A sender never calls a hand-off done on its own write. It waits for the
  receiver's own state to say `holding`, and it exits 4 when that never
  comes.
* A standby that was claimed is never offered again, even before it takes
  the frame, and even though its watcher has stopped beating.

Timing is short on purpose. The module's poll interval is monkeypatched
down, so each test costs a fraction of a second instead of a full beat.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

import handover
from handover import _write_json

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    """Poll fast, so a test waits in milliseconds and not in beats."""
    monkeypatch.setattr(handover, "POLL", 0.02)


@pytest.fixture
def box(tmp_path):
    """A mailbox under temp. No git repository, so the root is this directory."""
    return tmp_path


def run(box_path, *argv):
    """Call the tool the way a session calls it, and return its exit code.

    `hand` gets `--grace 0`, because the wait for a machine that just woke
    up is 25 seconds of real time and every test here would pay it.
    """
    argv = list(argv)
    if argv and argv[0] == "hand" and "--grace" not in argv:
        argv += ["--grace", "0"]
    return handover.main(["--root", str(box_path), *argv])


def until(predicate, timeout=5.0):
    """Wait for a fact. Return it, or fail the test with what was true instead."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    return None


def peer(box_path, sid):
    path = box_path / handover.BOX / "peers" / (sid + ".json")
    return json.loads(path.read_text(encoding="utf-8"))


def claim(box_path, sid):
    return box_path / handover.BOX / "claims" / (sid + ".json")


def age_the_arm(box_path, sid, seconds):
    """Move a registration back in time, so a scene reads as it would live.

    A reclaim evicts a registration only when it predates the claim, so a
    test that ages a claim must age the arm that saw it too. Otherwise the
    scene says a watcher armed after a claim it demonstrably answered.
    """
    api = handover.Box(box_path)
    state = api.read_state(sid)
    state["armed_at"] = time.time() - seconds
    state["since"] = state["armed_at"]
    api.write_state(sid, state)


def arm(box_path, sid, name="peer", wait=10.0):
    """Arm a standby in a thread, and return a handle that carries its exit code."""
    result = {}

    def target():
        result["code"] = run(box_path, "standby", "--sid", sid, "--name", name,
                             "--wait", str(wait), "--beat", "0.05")

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    assert until(lambda: (box_path / handover.BOX / "peers" / (sid + ".json")).exists()), \
        "the standby never registered"
    return thread, result


def test_one_claim_wakes_exactly_one_standby(box):
    """The reserve is the point. A hand-off spends one standby and no more."""
    threads = {}
    for sid in ("aaaa1111", "bbbb2222", "cccc3333"):
        threads[sid] = arm(box, sid)
        time.sleep(0.05)  # keep the arming order, so the queue order is known

    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--confirm", "0.2") == 4  # posted, and nobody took it

    claims = sorted(p.name for p in (box / handover.BOX / "claims").glob("*.json"))
    assert claims == ["aaaa1111.json"], "the oldest standby alone was claimed"

    woken, result = threads["aaaa1111"]
    woken.join(timeout=5)
    assert result["code"] == 0, "the claimed standby's watcher exited on the claim"

    for sid in ("bbbb2222", "cccc3333"):
        thread, other = threads[sid]
        assert thread.is_alive(), "an unclaimed standby keeps waiting"
        assert "code" not in other, "an unclaimed standby never woke"
        assert peer(box, sid)["state"] == "standby"


def test_two_senders_take_two_different_standbys(box):
    """Two sessions reach 400k together. Neither steals the other's peer."""
    for sid in ("aaaa1111", "bbbb2222"):
        arm(box, sid)
        time.sleep(0.05)

    codes, picked = [], []

    def send(frame):
        code = run(box, "hand", "--frame", frame, "--commit", "abc1234",
                   "--confirm", "0.1")
        codes.append(code)

    senders = [threading.Thread(target=send, args=(f,)) for f in ("8", "9")]
    for s in senders:
        s.start()
    for s in senders:
        s.join(timeout=10)

    for sid in ("aaaa1111", "bbbb2222"):
        if claim(box, sid).exists():
            picked.append(json.loads(claim(box, sid).read_text(encoding="utf-8"))["frame"])
    assert sorted(picked) == ["8", "9"], "each sender landed on its own standby"
    assert codes == [4, 4]


def test_a_second_claim_for_one_standby_is_refused(box, capsys):
    """A named peer that cannot take a frame is refused, and says why.

    It must not read as a drought. Posting a vacancy here would hide the
    fact that the Principal named a session that is already busy.
    """
    arm(box, "aaaa1111")
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--to", "aaaa1111", "--confirm", "0.1") == 4
    first = claim(box, "aaaa1111").read_text(encoding="utf-8")
    capsys.readouterr()
    assert run(box, "hand", "--frame", "8", "--commit", "def5678",
               "--to", "aaaa1111", "--confirm", "0.1") == 2
    out = capsys.readouterr().out
    assert "a claim already waits for it" in out
    assert "Nothing was handed off" in out
    assert claim(box, "aaaa1111").read_text(encoding="utf-8") == first, \
        "the losing sender changed nothing"
    assert not vacancies(box), "frame 8 was not quietly turned into a vacancy"


def test_an_exclusive_create_gives_one_winner_deterministically(box):
    """The named arbiter of the whole tool deserves a test with no threads."""
    path = box / handover.BOX
    path.mkdir(parents=True, exist_ok=True)
    target = path / "arbiter.json"
    first = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(first)
    with pytest.raises(FileExistsError):
        os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY)


def test_a_named_peer_that_is_not_in_the_reserve_is_refused(box, capsys):
    """The Principal named a session. A substitute answers a different question."""
    arm(box, "aaaa1111")
    capsys.readouterr()
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--to", "bbbb2222") == 2
    out = capsys.readouterr().out
    assert "names no session in the reserve" in out
    assert "aaaa1111" in out, "it names who is free instead"
    assert not vacancies(box)
    assert not list((box / handover.BOX / "claims").glob("*.json"))


def test_an_ambiguous_to_is_refused(box, capsys):
    """Two session ids can share a prefix, and the wrong peer must not win."""
    arm(box, "aaaa1111")
    arm(box, "aaaa2222")
    capsys.readouterr()
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--to", "aaaa") == 2
    out = capsys.readouterr().out
    assert "names 2 sessions" in out
    assert not list((box / handover.BOX / "claims").glob("*.json"))


def test_a_session_id_may_not_be_a_path(box):
    """`--sid ../../x` would write the mailbox outside the mailbox."""
    assert run(box, "take", "--sid", "../../escape") == 2
    assert run(box, "standby", "--sid", "a/b", "--wait", "1") == 2
    assert run(box, "release", "--sid", "..") == 2


def test_a_confirm_longer_than_the_tool_timeout_is_refused(box):
    """A sender killed mid-confirm can hand one frame to two sessions."""
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--confirm", "120") == 2
    assert not vacancies(box), "the refusal happens before anything is written"


def test_a_claimed_standby_is_not_offered_again(box):
    """A woken standby stops beating. The queue must not read that as free."""
    thread, _ = arm(box, "aaaa1111")
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--confirm", "0.1") == 4
    thread.join(timeout=5)

    rows = handover.Box(box).queue(handover.STALE)
    assert rows[0]["claimed"] is True
    assert rows[0]["free"] is False
    assert run(box, "peers") == 1, "no free standby is left"
    assert run(box, "hand", "--frame", "8", "--commit", "def5678",
               "--confirm", "0.1") == 5, "a second frame finds nobody"


def test_a_confirmed_hand_off_waits_for_the_receiver(box):
    """The proof is the receiver's own state, and never the sender's write."""
    thread, _ = arm(box, "aaaa1111")

    def receiver():
        assert until(lambda: claim(box, "aaaa1111").exists())
        run(box, "take", "--sid", "aaaa1111")

    taker = threading.Thread(target=receiver)
    taker.start()
    code = run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--sender", "ffff9999", "--confirm", "5")
    taker.join(timeout=10)
    thread.join(timeout=5)

    assert code == 0, "the sender saw the take and only then stopped"
    held = peer(box, "aaaa1111")
    assert held["state"] == "holding"
    assert held["frame"] == "7"
    assert held["from_sid"] == "ffff9999"


def vacancies(box_path):
    return sorted((box_path / handover.BOX / "waiting").glob("*.json"))


def test_a_hand_off_with_no_standby_fails_loudly(box, capsys):
    """No reserve is not a silent case. The frame stays open and says so."""
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234") == 5
    out = capsys.readouterr().out
    assert "NO FREE STANDBY" in out
    assert "commit the stack" in out
    assert len(vacancies(box)) == 1, \
        "the drought leaves the hand-off on disk, not only in a status line"


def test_two_droughts_of_one_frame_keep_both_vacancies(box):
    """A fixed file name per frame would erase the first hand-off in silence."""
    assert run(box, "hand", "--frame", "7", "--commit", "aaa1111") == 5
    assert run(box, "hand", "--frame", "7", "--commit", "bbb2222") == 5
    posted = [json.loads(p.read_text(encoding="utf-8"))["commit"]
              for p in vacancies(box)]
    assert sorted(posted) == ["aaa1111", "bbb2222"], "neither vacancy was lost"


def test_a_standby_armed_after_the_drought_takes_the_waiting_frame(box):
    """The Principal opens a session in the morning. The night's frame is there."""
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--sender", "ffff9999") == 5

    thread, result = arm(box, "aaaa1111", wait=10)
    thread.join(timeout=5)
    assert result["code"] == 0, "the fresh standby woke at once, with no blocking"
    assert not vacancies(box), \
        "the vacancy is consumed, so no second session takes the same frame"

    assert run(box, "take", "--sid", "aaaa1111") == 0
    assert peer(box, "aaaa1111")["frame"] == "7"


def test_two_sessions_armed_together_cannot_both_take_one_vacancy(box):
    """A rename has one winner. The loser stays a clean standby."""
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234") == 5

    started = {}
    for sid in ("aaaa1111", "bbbb2222"):
        started[sid] = arm(box, sid, wait=3)

    claims = until(lambda: sorted(
        p.name for p in (box / handover.BOX / "claims").glob("*.json")) or None)
    assert len(claims) == 1, "one vacancy filled exactly one claim"
    winner = claims[0].replace(".json", "")
    loser = "bbbb2222" if winner == "aaaa1111" else "aaaa1111"

    started[winner][0].join(timeout=5)
    assert started[winner][1]["code"] == 0
    assert started[loser][0].is_alive(), "the loser is still a standby, still clean"

    run(box, "release", "--sid", loser)  # so no watcher outlives the test
    started[loser][0].join(timeout=5)


def test_a_session_that_never_arms_can_still_see_the_waiting_frame(box, capsys):
    """A session started for other work must not walk past an orphaned frame."""
    run(box, "hand", "--frame", "7", "--commit", "abc1234", "--sender", "ffff9999")
    assert run(box, "peers") == 1, "no free standby, so the exit code still warns"
    out = capsys.readouterr().out
    assert "WAITING: frame 7" in out
    assert "abc1234" in out


def test_a_stale_heartbeat_is_not_a_standby(box):
    """A session that died leaves its file behind. The clock finds it out."""
    api = handover.Box(box)
    api.write_state("dddd4444", {
        "sid": "dddd4444", "name": "gone", "since": time.time() - 9000,
        "since_iso": "then", "beat": time.time() - handover.STALE - 30,
        "state": "standby", "frame": None,
    })
    assert run(box, "peers") == 1
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234") == 5


def test_take_without_a_claim_says_so(box, capsys):
    """A woken session that finds no claim must re-arm, not invent work."""
    assert run(box, "take", "--sid", "aaaa1111") == 1
    assert "Arm the watcher again" in capsys.readouterr().out


def test_release_empties_the_seat(box):
    """A standby that became a worker leaves the reserve, watcher and all.

    A live watcher writes its heartbeat again after a deletion, so this
    test failed the first time it ran beside the rest of the suite. The
    watcher now exits when its registration is gone.
    """
    thread, result = arm(box, "aaaa1111", wait=10)
    assert run(box, "release", "--sid", "aaaa1111") == 0
    thread.join(timeout=5)
    assert result.get("code") == 1, "the watcher stopped instead of beating on"
    assert not (box / handover.BOX / "peers" / "aaaa1111.json").exists()
    assert run(box, "release", "--sid", "aaaa1111") == 1


def test_the_audit_line_survives_a_failed_hand_off(box):
    """A hand-off that never landed must still be readable afterwards."""
    run(box, "hand", "--frame", "7", "--commit", "abc1234")
    events = [json.loads(line)["event"]
              for line in (box / handover.BOX / "log.jsonl").read_text(
                  encoding="utf-8").splitlines()]
    assert "no_standby" in events


def test_a_state_write_leaves_no_temporary_file(box):
    """A directory full of half-written state would make the queue unreadable."""
    api = handover.Box(box)
    for n in range(5):
        api.write_state("aaaa1111", {"sid": "aaaa1111", "since": 1, "beat": n,
                                     "state": "standby", "frame": None})
    assert sorted(p.suffix for p in api.peers.iterdir()) == [".json"]


def test_one_box_serves_the_whole_checkout(tmp_path):
    """Every session in one repository shares one reserve, from any directory."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True, env={
        **GIT_ENV, "PATH": __import__("os").environ["PATH"]})
    deep = tmp_path / "plans" / "archive"
    deep.mkdir(parents=True)
    handover.main(["--root", str(deep), "peers"])
    assert (tmp_path / handover.BOX / "peers").is_dir(), \
        "the box sits at the repository root, not beside the caller"
    assert not (deep / handover.BOX).exists()


def test_a_session_that_holds_a_frame_cannot_rejoin_the_reserve(box, capsys):
    """Otherwise a session holding frame 43 is handed frame 44 as well."""
    arm(box, "aaaa1111")
    run(box, "hand", "--frame", "43", "--commit", "abc1234", "--confirm", "0.1")
    run(box, "take", "--sid", "aaaa1111")
    capsys.readouterr()
    assert run(box, "standby", "--sid", "aaaa1111", "--wait", "1") == 2
    assert "holds frame 43 already" in capsys.readouterr().out
    assert peer(box, "aaaa1111")["state"] == "holding", "the frame stayed held"


def test_a_take_cannot_happen_twice(box):
    """The claim moves into a receipt, so a second take has nothing to read."""
    arm(box, "aaaa1111")
    run(box, "hand", "--frame", "7", "--commit", "abc1234", "--confirm", "0.1")
    assert run(box, "take", "--sid", "aaaa1111") == 0
    assert not claim(box, "aaaa1111").exists(), "the claim was consumed"
    receipts = list((box / handover.BOX / "taken").glob("*.json"))
    assert len(receipts) == 1 and "aaaa1111" in receipts[0].name
    assert run(box, "take", "--sid", "aaaa1111") == 1


def test_an_unread_claim_returns_to_the_queue(box, capsys):
    """A session can wake and fail to act. The frame must not wait for a person."""
    arm(box, "aaaa1111")
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--confirm", "0.1") == 4
    path = claim(box, "aaaa1111")
    stale_claim = json.loads(path.read_text(encoding="utf-8"))
    stale_claim["t"] = time.time() - 3600
    path.write_text(json.dumps(stale_claim), encoding="utf-8")
    age_the_arm(box, "aaaa1111", 7200)   # the watcher armed before the claim
    capsys.readouterr()

    run(box, "peers", "--reclaim", "60")
    out = capsys.readouterr().out
    assert "RECLAIMED: frame 7" in out
    assert not path.exists(), "the claim left the claims directory"
    assert len(vacancies(box)) == 1, "the frame is back in the queue"
    assert json.loads(vacancies(box)[0].read_text(encoding="utf-8"))["commit"] == "abc1234"
    assert not (box / handover.BOX / "peers" / "aaaa1111.json").exists(), \
        "the session whose watcher already exited left the reserve"


def test_a_reclaim_does_not_offer_the_dead_watcher_again(box):
    """Its watcher exited when the claim appeared, so it waits for nothing.

    The heartbeat can still read fresh, and a sender would then hand the
    frame straight back to a session that nothing is watching.
    """
    thread, _ = arm(box, "aaaa1111", wait=10)
    run(box, "hand", "--frame", "7", "--commit", "abc1234", "--confirm", "0.1")
    thread.join(timeout=5)
    path = claim(box, "aaaa1111")
    aged = json.loads(path.read_text(encoding="utf-8"))
    aged["t"] = time.time() - 3600
    path.write_text(json.dumps(aged), encoding="utf-8")
    age_the_arm(box, "aaaa1111", 7200)   # the watcher armed before the claim

    api = handover.Box(box)
    assert len(api.reclaim(60)) == 1
    assert [r for r in api.queue(handover.STALE) if r["free"]] == [], \
        "no free standby is left, however fresh the heartbeat looked"
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234") == 5, \
        "the frame waits as a vacancy instead of going to a dead watcher"


def test_a_taken_frame_is_never_reclaimed(box):
    """A receipt stops the clock. Otherwise a working session loses its frame."""
    arm(box, "aaaa1111")
    run(box, "hand", "--frame", "7", "--commit", "abc1234", "--confirm", "0.1")
    run(box, "take", "--sid", "aaaa1111")
    assert handover.Box(box).reclaim(0.001) == [], "nothing to reclaim after a take"
    assert not vacancies(box)


def test_a_vacancy_goes_back_when_a_sender_wins_the_race(box, monkeypatch):
    """The window between the check and the rename must not eat a frame."""
    run(box, "hand", "--frame", "7", "--commit", "abc1234")
    api = handover.Box(box)
    real_rename = handover.os.rename

    def rename_then_race(src, dst):
        real_rename(src, dst)
        # A sender claims this session in the same instant.
        api.claim_file("aaaa1111").write_text('{"frame":"99"}', encoding="utf-8")
        monkeypatch.setattr(handover.os, "rename", real_rename)

    monkeypatch.setattr(handover.os, "rename", rename_then_race)
    assert handover._consume_vacancy(api, "aaaa1111") is None
    assert len(vacancies(box)) == 1, "frame 7 went back to the queue"
    assert json.loads(claim(box, "aaaa1111").read_text(
        encoding="utf-8"))["frame"] == "99", "the sender's claim survived"


def test_a_wall_clock_step_does_not_end_a_wait(box, monkeypatch):
    """An NTP correction must not end a block early. Deadlines are monotonic."""
    offset = {"v": 0.0}
    real_time = time.time
    monkeypatch.setattr(handover.time, "time", lambda: real_time() + offset["v"])

    result = {}

    def target():
        result["code"] = run(box, "standby", "--sid", "aaaa1111",
                             "--wait", "2", "--beat", "0.1")

    thread = threading.Thread(target=target, daemon=True)
    started = time.monotonic()
    thread.start()
    assert until(lambda: (box / handover.BOX / "peers" / "aaaa1111.json").exists())
    offset["v"] = 86400.0  # the clock jumps a day forward mid-wait
    thread.join(timeout=10)
    assert result.get("code") == 3
    assert time.monotonic() - started >= 1.5, \
        "the watcher kept waiting through the clock step"


def test_a_worktree_shares_the_reserve_with_its_checkout(tmp_path):
    """The brief reviews a diff in a worktree. A second reserve there is invisible."""
    import os as _os
    env = {**GIT_ENV, "PATH": _os.environ["PATH"]}
    main = tmp_path / "main"
    main.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(main), check=True, env=env)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"],
                   cwd=str(main), check=True, env=env)
    tree = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", str(tree)],
                   cwd=str(main), check=True, env=env)

    handover.main(["--root", str(tree), "peers"])
    assert (main / handover.BOX / "peers").is_dir(), \
        "a session in a worktree registers in the checkout's reserve"
    assert not (tree / handover.BOX).exists(), "and not in a reserve of its own"


def test_a_file_that_will_not_parse_is_not_an_absent_file(box):
    """The measured defect: a locked claim read as "no claim waits, continue"."""
    api = handover.Box(box)
    path = api.claim_file("aaaa1111")
    path.write_text("not json at all [", encoding="utf-8")
    with pytest.raises(handover.Unreadable):
        handover._read_json(path)
    path.write_text('["a list, not an object"]', encoding="utf-8")
    with pytest.raises(handover.Unreadable):
        handover._read_json(path)
    assert handover._read_json(api.claim_file("nobody")) is None, \
        "an absent file is still None"


def test_take_on_an_unreadable_claim_says_retry_and_not_continue(box, capsys):
    """Exit 1 would send the session off to other work, past a live frame."""
    api = handover.Box(box)
    api.claim_file("aaaa1111").write_text("{ broken", encoding="utf-8")
    assert run(box, "take", "--sid", "aaaa1111") == 6
    out = capsys.readouterr().out
    assert "will not open" in out
    assert "Do not take other work" in out


def test_an_unreadable_row_is_skipped_and_named(box, capsys):
    """One bad file must not stop the queue, and must not vanish either."""
    api = handover.Box(box)
    arm(box, "aaaa1111")
    (api.peers / "bbbb2222.json").write_text("{ broken", encoding="utf-8")
    capsys.readouterr()
    run(box, "peers")
    out = capsys.readouterr().out
    assert "aaaa1111" in out, "the good row still printed"
    assert "UNREADABLE: bbbb2222.json" in out


def test_release_gives_an_unread_frame_back(box, capsys):
    """Deleting the claim would end a hand-off with a line that says success."""
    arm(box, "aaaa1111")
    run(box, "hand", "--frame", "7", "--commit", "abc1234", "--confirm", "0.1")
    capsys.readouterr()
    assert run(box, "release", "--sid", "aaaa1111") == 0
    out = capsys.readouterr().out
    assert "frame 7 was claimed and unread" in out
    assert len(vacancies(box)) == 1, "the frame is back in the queue"


def test_a_heartbeat_from_the_future_is_not_live(box):
    """Two machines on one checkout would otherwise keep a dead row free."""
    api = handover.Box(box)
    api.write_state("dddd4444", {
        "sid": "dddd4444", "name": "ahead", "since": time.time(),
        "since_iso": "now", "beat": time.time() + 7200,
        "state": "standby", "frame": None,
    })
    row = api.queue(handover.STALE)[0]
    assert row["live"] is False and row["ahead"] is True
    assert run(box, "peers") == 1
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234") == 5


def test_a_blocked_standby_picks_up_a_vacancy(box):
    """A reclaim posts a vacancy while standbys already wait. One must take it."""
    thread, result = arm(box, "aaaa1111", wait=10)
    api = handover.Box(box)
    api._post({"frame": "9", "commit": "def5678", "from_sid": "ffff9999",
               "t": time.time(), "iso": "now"})
    thread.join(timeout=10)
    assert result.get("code") == 0, "the waiting standby woke on the vacancy"
    assert not vacancies(box)
    assert run(box, "take", "--sid", "aaaa1111") == 0
    assert peer(box, "aaaa1111")["frame"] == "9"


def test_take_accepts_a_hand_off_that_names_nobody(box, capsys):
    """The hook orders every session to take a waiting frame. This obeys it."""
    run(box, "hand", "--frame", "7", "--commit", "abc1234")
    capsys.readouterr()
    assert run(box, "take", "--sid", "cccc3333") == 0
    out = capsys.readouterr().out
    assert "no claim named you" in out
    assert "frame 7" in out
    assert not vacancies(box), "it was consumed, so no second session takes it"


def test_drop_cancels_a_vacancy(box, capsys):
    """A frame the Principal closed by hand must stop being ordered."""
    run(box, "hand", "--frame", "7", "--commit", "abc1234")
    capsys.readouterr()
    assert run(box, "drop", "--frame", "8") == 1
    assert run(box, "drop", "--frame", "7", "--reason", "closed by hand") == 0
    assert not vacancies(box)
    assert run(box, "drop", "--frame", "7") == 1
    events = [json.loads(line)["event"] for line in
              (box / handover.BOX / "log.jsonl").read_text(
                  encoding="utf-8").splitlines()]
    assert "vacancy_dropped" in events


def test_a_re_armed_watcher_takes_an_unread_claim_at_once(box):
    """Why the feared case does not arise, recorded so nobody re-argues it.

    A watcher times out, a claim lands while nothing is blocking, and the
    session re-arms as it is told to. The fear was that the reclaim would
    later evict that healthy session. It cannot: the new watcher reads the
    waiting claim on its first poll and exits, so the claim is gone long
    before any reclaim clock runs out. The self-heal is the defence, and
    the guard below is only the belt.
    """
    api = handover.Box(box)
    _write_json(api.claim_file("aaaa1111"),
                {"frame": "7", "commit": "abc1234", "from_sid": "ffff9999",
                 "t": time.time() - 3600, "iso": "an hour ago"})

    thread, result = arm(box, "aaaa1111", wait=10)
    thread.join(timeout=5)
    assert result.get("code") == 0, "the re-armed watcher woke on the old claim"
    assert run(box, "take", "--sid", "aaaa1111") == 0
    assert peer(box, "aaaa1111")["frame"] == "7"


def test_a_reclaim_evicts_only_a_registration_older_than_the_claim(box):
    """The eviction checks the assumption its comment used to assert.

    Evicting says "the watcher that was blocking saw this claim and
    exited". That holds only when the registration predates the claim. A
    newer registration belongs to a watcher that never saw it.
    """
    api = handover.Box(box)
    now = time.time()

    def scene(sid, armed_at):
        api.write_state(sid, {"sid": sid, "since": armed_at, "since_iso": "then",
                              "armed_at": armed_at, "beat": armed_at,
                              "state": "standby", "frame": None})
        _write_json(api.claim_file(sid),
                    {"frame": "7", "commit": "abc1234", "t": now - 3600,
                     "iso": "an hour ago"})

    scene("aaaa1111", now - 7200)      # armed before the claim: spent
    scene("bbbb2222", now - 60)        # armed after it: a live watcher's seat
    assert len(api.reclaim(60)) == 2, "both frames go back to the queue"
    assert not api.peer_file("aaaa1111").exists()
    assert api.peer_file("bbbb2222").exists(), "the newer registration survived"


def test_a_newer_watcher_retires_the_older_one(box):
    """One session, one watcher. Two would race for one claim."""
    first, first_result = arm(box, "aaaa1111", wait=10)
    time.sleep(0.05)
    second, second_result = arm(box, "aaaa1111", wait=10)

    first.join(timeout=5)
    assert first_result.get("code") == 1, "the older watcher stood down"
    assert second.is_alive(), "the newer one kept the seat"
    assert handover.Box(box).peer_file("aaaa1111").exists()

    run(box, "release", "--sid", "aaaa1111")
    second.join(timeout=5)


def test_a_cleared_frame_does_not_make_a_session_a_standby(box, capsys):
    """Its watcher exited when it took the frame. Nothing watches for it now.

    Reported from a live frame: a session closed its frame, cleared the
    column, and the table printed it as a standby with a dead heartbeat.
    The legend reads that as a session that died, and it was working. The
    same fault class as a holder printed STALE.
    """
    thread, _ = arm(box, "aaaa1111", wait=10)
    run(box, "hand", "--frame", "50", "--commit", "abc1234", "--confirm", "0.1")
    thread.join(timeout=5)                      # the watcher exits on the claim
    run(box, "take", "--sid", "aaaa1111")
    capsys.readouterr()

    assert run(box, "holding", "--sid", "aaaa1111", "--frame", "none") == 0
    out = capsys.readouterr().out
    assert "no watcher runs for you" in out
    assert "Arm again" in out

    state = peer(box, "aaaa1111")
    assert state["frame"] is None
    assert state["state"] != "standby", "a session does not become a standby by saying so"

    run(box, "peers")
    table = capsys.readouterr().out
    row = [line for line in table.splitlines() if line.startswith("aaaa1111")][0]
    assert "spent" in row and "STALE" not in row
    assert "0 free standby" in table, "a spent row is never offered a frame"


def test_a_standby_that_really_died_still_reads_stale(box):
    """The fix must not hide the case the STALE column exists for."""
    api = handover.Box(box)
    api.write_state("dddd4444", {
        "sid": "dddd4444", "name": "gone", "since": time.time() - 9000,
        "since_iso": "then", "armed_at": time.time() - 9000,
        "beat": time.time() - handover.STALE - 30,
        "state": "standby", "frame": None,
    })
    row = api.queue(handover.STALE)[0]
    assert row["live"] is False and row["free"] is False
    assert run(box, "peers") == 1


def enrol(box_path, sid, est):
    """Write what the context hook writes, so a row carries an estimate."""
    api = handover.Box(box_path)
    _write_json(api.sessions / (sid + ".json"),
                {"sid": sid, "name": "peer-" + sid[:4], "est": est,
                 "turns": 1, "t": time.time()})


def test_a_frame_goes_to_the_oldest_standby_under_the_ceiling(box):
    """Use a session up before spending a fresh one, but never past 300k."""
    arm(box, "aaaa1111")          # oldest, and too full to finish a frame
    time.sleep(0.05)
    arm(box, "bbbb2222")          # next oldest, and able to
    time.sleep(0.05)
    arm(box, "cccc3333")          # freshest, and should stay unspent
    enrol(box, "aaaa1111", 340)
    enrol(box, "bbbb2222", 210)
    enrol(box, "cccc3333", 20)

    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--confirm", "0.1") == 4
    claims = sorted(p.stem for p in (box / handover.BOX / "claims").glob("*.json"))
    assert claims == ["bbbb2222"], \
        "the oldest one under the ceiling took it, not the oldest and not the cleanest"


def test_an_unknown_estimate_is_the_cleanest_standby_there_is(box):
    """A window armed on its first prompt has no transcript to measure yet.

    It stays unmeasured for as long as it sits quiet, so unknown is the
    normal state of the best seat in the reserve. Observed in the wild:
    a live session enrolled with est null and turns zero.
    """
    arm(box, "aaaa1111")
    enrol(box, "aaaa1111", None)
    row = [r for r in handover.Box(box).queue(handover.STALE)
           if r["sid"] == "aaaa1111"][0]
    assert row["over"] is False and row["free"] is True
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--confirm", "0.1") == 4


def test_a_reserve_that_is_all_too_full_is_a_drought(box, capsys):
    """And it must not read as an empty reserve, which is a different fact."""
    arm(box, "aaaa1111")
    enrol(box, "aaaa1111", 340)
    capsys.readouterr()

    assert run(box, "hand", "--frame", "7", "--commit", "abc1234") == 5
    out = capsys.readouterr().out
    assert "over the 300k ceiling" in out
    assert "aaaa1111 at 340k" in out
    assert "not an empty reserve" in out
    assert len(vacancies(box)) == 1, "the frame waits for a fresh window"


def test_a_session_past_the_ceiling_leaves_instead_of_arming(box, capsys):
    """A seat it holds is a seat no hand-off can use."""
    enrol(box, "dddd4444", 355)
    capsys.readouterr()
    assert run(box, "standby", "--sid", "dddd4444", "--wait", "1") == 2
    out = capsys.readouterr().out
    assert "past the 300k ceiling" in out
    assert "left the reserve" in out
    assert not (box / handover.BOX / "peers" / "dddd4444.json").exists()


def test_the_hook_name_beats_the_typed_name(box):
    """A session cannot know its own peer name, so its guess must not win.

    Reported from a live frame: a session typed a description as its
    name, `peers` printed it, and a peer wanting to use the message
    fallback would have addressed a name that reaches nobody.
    """
    arm(box, "aaaa1111", name="Opus5-standby")
    api = handover.Box(box)
    _write_json(api.sessions / "aaaa1111.json",
                {"sid": "aaaa1111", "name": "rota-52", "est": 12, "t": time.time()})
    row = [r for r in api.queue(handover.STALE) if r["sid"] == "aaaa1111"][0]
    assert row["name"] == "rota-52", "the registry name the hook wrote wins"
    assert row["est"] == 12


def test_a_typed_name_still_serves_a_checkout_with_no_hook(box):
    """The hook is the kit's, and a destination may not have installed it."""
    arm(box, "aaaa1111", name="typed-only")
    row = [r for r in handover.Box(box).queue(handover.STALE)
           if r["sid"] == "aaaa1111"][0]
    assert row["name"] == "typed-only"


def test_a_holder_is_not_printed_as_stale(box, capsys):
    """Its watcher exits when it delivers the claim, so the beat stops by design.

    Reported from a live frame: a working session read STALE for an hour,
    which says the session died.
    """
    arm(box, "aaaa1111")
    run(box, "hand", "--frame", "7", "--commit", "abc1234", "--confirm", "0.1")
    run(box, "take", "--sid", "aaaa1111")
    api = handover.Box(box)
    state = api.read_state("aaaa1111")
    state["beat"] = time.time() - 9000          # an hour of honest silence
    api.write_state("aaaa1111", state)
    capsys.readouterr()

    run(box, "peers")
    out = capsys.readouterr().out
    row = [line for line in out.splitlines() if line.startswith("aaaa1111")][0]
    assert "held" in row and "STALE" not in row
    assert "handed" in out, "the column says what it means"


def test_holding_corrects_the_handed_column(box, capsys):
    """A row that contradicts the stack sends a reader to the wrong place."""
    arm(box, "aaaa1111")
    run(box, "hand", "--frame", "43", "--commit", "abc1234", "--confirm", "0.1")
    run(box, "take", "--sid", "aaaa1111")
    assert peer(box, "aaaa1111")["frame"] == "43"
    capsys.readouterr()

    assert run(box, "holding", "--sid", "aaaa1111", "--frame", "46") == 0
    assert "was 43, and now reads 46" in capsys.readouterr().out
    assert peer(box, "aaaa1111")["frame"] == "46"

    assert run(box, "holding", "--sid", "aaaa1111", "--frame", "none") == 0
    assert peer(box, "aaaa1111")["frame"] is None
    assert peer(box, "aaaa1111")["state"] != "standby",         "clearing a frame does not arm a watcher, so it does not make a standby"
    assert run(box, "holding", "--sid", "bbbb2222", "--frame", "1") == 1


def test_the_sid_decides_the_address_and_not_the_name(box):
    """A peer name changes when a session restarts. The session id does not."""
    arm(box, "aaaa1111", name="meta-workflow-46")
    api = handover.Box(box)
    state = api.read_state("aaaa1111")
    state["name"] = "meta-workflow-91"  # the harness renamed the session
    api.write_state("aaaa1111", state)
    assert run(box, "hand", "--frame", "7", "--commit", "abc1234",
               "--to", "aaaa1111", "--confirm", "0.1") == 4
    assert claim(box, "aaaa1111").exists()
