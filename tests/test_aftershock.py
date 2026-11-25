import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from aftershock.check import check, matches
from aftershock.cli import main
from aftershock.report import markdown, summary
from aftershock.runner import Task, run, sweep
from aftershock.world import FAULT_KINDS, Fault, World

DEMO = Path(__file__).resolve().parent.parent / "aftershock" / "demo"
TASK = Task.load(DEMO / "invoice.json")


def agent(name):
    return [sys.executable, str(DEMO / "agents" / f"{name}.py")]


def kinds_of(r):
    return sorted(p["kind"] for p in r.verdict.problems)


# -- the world ---------------------------------------------------------------

def test_idempotency_key_replays_without_second_effect():
    w = World()
    s1, b1, _ = w.call("charge", {"customer": "c", "amount": 5}, "k1")
    s2, b2, _ = w.call("charge", {"customer": "c", "amount": 5}, "k1")
    assert (s1, s2) == (200, 200) and b1 == b2
    assert len(w.effects) == 1 and w.calls[1]["replayed"]


def test_no_key_means_second_effect():
    w = World()
    w.call("charge", {"customer": "c", "amount": 5}, None)
    w.call("charge", {"customer": "c", "amount": 5}, None)
    assert len(w.effects) == 2


def test_fault_fires_once_on_its_call():
    w = World(faults=(Fault("error", 2),))
    assert w.call("lookup_customer", {"customer": "x"}, None)[0] == 200
    assert w.call("charge", {"customer": "c", "amount": 1}, None)[0] == 503
    assert w.call("charge", {"customer": "c", "amount": 1}, None)[0] == 200
    assert len(w.effects) == 1


def test_crash_after_applies_then_kills():
    w = World(faults=(Fault("crash-after", 1),))
    status, _, kill = w.call("send_email", {"to": "a@b", "subject": "s"}, None)
    assert kill and status is None and len(w.effects) == 1


def test_crash_before_does_not_apply():
    w = World(faults=(Fault("crash-before", 1),))
    _, _, kill = w.call("send_email", {"to": "a@b", "subject": "s"}, None)
    assert kill and not w.effects


def test_timeout_applies_but_reports_failure():
    w = World(faults=(Fault("timeout", 1),))
    status, _, kill = w.call("charge", {"customer": "c", "amount": 1}, None)
    assert status == 504 and not kill and len(w.effects) == 1


def test_bad_calls_are_refused_and_not_applied():
    w = World()
    assert w.call("nope", {}, None)[0] == 404
    assert w.call("charge", {"customer": "c"}, None)[0] == 400
    assert not w.effects


def test_find_charges_sees_earlier_charges():
    w = World()
    w.call("charge", {"customer": "c", "amount": 1}, None)
    _, body, _ = w.call("find_charges", {"customer": "c"}, None)
    assert len(body["charges"]) == 1


def test_fault_parse():
    assert Fault.parse("crash-after@3") == Fault("crash-after", 3)
    for bad in ("crash-after", "melt@2", "error@0"):
        with pytest.raises(ValueError):
            Fault.parse(bad)


# -- checking ----------------------------------------------------------------

def test_amount_matches_across_formats():
    exp = {"tool": "charge", "match": {"customer": "cus_42", "amount": 120}}
    for amt in (120, "120", "120.00", "£120"):
        assert matches(exp, {"tool": "charge", "args": {"customer": "CUS_42", "amount": amt}})
    assert not matches(exp, {"tool": "charge", "args": {"customer": "cus_42", "amount": 12000}})


def test_check_flags_missing_duplicate_unexpected_unfinished():
    w = World()
    w.call("charge", {"customer": "cus_42", "amount": 120}, None)
    w.call("charge", {"customer": "cus_42", "amount": 120}, None)
    w.call("send_email", {"to": "eve@example.com", "subject": "x"}, None)
    v = check(TASK, w, [{"exit": 1}])
    assert sorted(p["kind"] for p in v.problems) == [
        "duplicate", "missing", "missing", "unexpected", "unfinished"]


def test_repeat_ok_allows_rewriting_a_file():
    w = World()
    for _ in range(2):
        w.call("write_file", {"path": "invoices/cus_42-nov.txt", "content": "x"}, None)
    v = check(TASK, w, [{"exit": 0}])
    assert "duplicate" not in [p["kind"] for p in v.problems]


def test_task_rejects_read_tools_in_expect(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"name": "x", "prompt": "x", "expect": [{"tool": "find_charges"}]}))
    with pytest.raises(ValueError):
        Task.load(p)


# -- whole runs with the demo agents -----------------------------------------

@pytest.mark.parametrize("name", ["naive", "resumes", "safe"])
def test_clean_run_passes(name):
    r = run(TASK, agent(name), timeout=20)
    assert r.passed, r.verdict.problems
    assert [c["tool"] for c in r.world.calls] == ["lookup_customer", "charge", "send_email", "write_file"]


def test_naive_double_charges_after_lost_reply():
    r = run(TASK, agent("naive"), Fault("crash-after", 2), timeout=20)
    assert kinds_of(r) == ["duplicate"]
    assert r.attempts[0]["killed"] and r.attempts[-1]["exit"] == 0


def test_naive_double_charges_when_crashed_later():
    r = run(TASK, agent("naive"), Fault("crash-before", 3), timeout=20)
    assert kinds_of(r) == ["duplicate"]


def test_resumes_survives_crash_before():
    for at in range(1, 5):
        assert run(TASK, agent("resumes"), Fault("crash-before", at), timeout=20).passed


@pytest.mark.parametrize("fault", ["crash-after@2", "timeout@2", "crash-after@3", "timeout@3"])
def test_resumes_still_duplicates_when_reply_lost(fault):
    r = run(TASK, agent("resumes"), Fault.parse(fault), timeout=20)
    assert kinds_of(r) == ["duplicate"]


def test_safe_passes_full_sweep():
    res = sweep(TASK, agent("safe"), timeout=20)
    assert len(res) == 1 + 4 * len(FAULT_KINDS)
    assert all(r.passed for r in res), [r.verdict.problems for r in res if not r.passed]


def test_agent_that_always_crashes_is_unfinished(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("import sys; sys.exit(3)")
    r = run(TASK, [sys.executable, str(bad)], max_restarts=1, timeout=10)
    assert len(r.attempts) == 2
    assert "unfinished" in kinds_of(r)


def test_timeout_is_reported(tmp_path):
    slow = tmp_path / "slow.py"
    slow.write_text("import time; time.sleep(30)")
    r = run(TASK, [sys.executable, str(slow)], max_restarts=0, timeout=0.5)
    assert r.attempts[0]["exit"] == "timeout" and not r.passed


# -- reports and CLI ---------------------------------------------------------

def test_summary_and_markdown_name_the_failures():
    res = sweep(TASK, agent("resumes"), ["crash-after"], timeout=20)
    text = summary(res)
    assert "2 of 4 crash tests passed" in text
    assert "charge cus_42 120" in text
    md = markdown(res, TASK.name)
    assert "| 2 | charge |" in md and "**FAIL**" in md


def test_cli_run_exit_codes(capsys):
    assert main(["run", str(DEMO / "invoice.json"), "--", *agent("safe")]) == 0
    assert main(["run", str(DEMO / "invoice.json"), "--fault", "crash-after@2", "--", *agent("naive")]) == 1
    assert "FAIL" in capsys.readouterr().out
    assert main(["run", str(DEMO / "invoice.json"), "--fault", "melt@1", "--", *agent("safe")]) == 2
    assert main(["run", "missing.json", "--", *agent("safe")]) == 2


def test_cli_sweep_writes_files(tmp_path):
    js, md = tmp_path / "r.json", tmp_path / "r.md"
    code = main(["sweep", str(DEMO / "invoice.json"), "--faults", "timeout",
                 "--json", str(js), "--md", str(md), "--", *agent("safe")])
    assert code == 0
    data = json.loads(js.read_text())
    assert len(data) == 5 and all(d["passed"] for d in data)
    assert md.read_text().startswith("## Bill a customer")


def test_cli_demo(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "16 of 16 crash tests passed" in out  # safe
    assert "naive" in out and "FAIL" in out


# -- the language-model agent, against a scripted stand-in for Ollama --------

SCRIPT = [
    {"tool": "lookup_customer", "args": {"customer": "cus_42"}},
    {"tool": "charge", "args": {"customer": "cus_42", "amount": 120, "description": "November"}},
    {"tool": "send_email", "args": {"to": "ana@example.com", "subject": "Receipt", "body": "£120"}},
    {"tool": "write_file", "args": {"path": "invoices/cus_42-nov.txt", "content": "£120"}},
    {"done": "billed"},
]


@pytest.fixture
def fake_ollama():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            turn = sum(m["role"] == "assistant" for m in body["messages"])
            reply = json.dumps(SCRIPT[min(turn, len(SCRIPT) - 1)])
            data = json.dumps({"message": {"role": "assistant", "content": reply}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


def test_llm_agent_clean_run(fake_ollama):
    r = run(TASK, agent("llm"), env={"OLLAMA_URL": fake_ollama}, timeout=20)
    assert r.passed, (r.verdict.problems, r.attempts)


def test_llm_agent_without_memory_redoes_everything(fake_ollama):
    r = run(TASK, agent("llm"), Fault("crash-before", 3), env={"OLLAMA_URL": fake_ollama}, timeout=20)
    assert kinds_of(r) == ["duplicate"]


def test_llm_agent_with_memory_resumes(fake_ollama):
    env = {"OLLAMA_URL": fake_ollama, "AFTERSHOCK_MEMORY": "1"}
    assert run(TASK, agent("llm"), Fault("crash-before", 3), env=env, timeout=20).passed
    # ...but the lost reply still costs a second charge
    assert kinds_of(run(TASK, agent("llm"), Fault("crash-after", 2), env=env, timeout=20)) == ["duplicate"]


# -- two faults in one run ---------------------------------------------------

def test_parse_many_sorts_and_rejects_clashes():
    assert Fault.parse_many("timeout@5, crash-after@2") == (Fault("crash-after", 2), Fault("timeout", 5))
    for bad in ("", "error@2,timeout@2", "error@2,melt@3"):
        with pytest.raises(ValueError):
            Fault.parse_many(bad)


def test_world_fires_each_fault_once():
    w = World(faults=(Fault("error", 1), Fault("error", 2)))
    codes = [w.call("charge", {"customer": "c", "amount": 1}, None)[0] for _ in range(3)]
    assert codes == [503, 503, 200] and len(w.effects) == 1


def test_plan_counts():
    from aftershock.runner import plan
    assert len(plan(4)) == 16
    assert len(plan(4, double=True)) == 16 + 4 * 4 * 4 * 4
    assert len(plan(3, ["error"], double=True)) == 3 + 3 * 3


def test_safe_survives_two_lost_replies():
    r = run(TASK, agent("safe"), Fault.parse_many("crash-after@2,crash-after@4"), timeout=20)
    assert r.passed and r.all_fired and len(r.attempts) == 3


def test_second_fault_that_never_fires_is_reported():
    r = run(TASK, agent("safe"), Fault.parse_many("error@2,error@99"), timeout=20)
    assert r.passed and not r.all_fired


RETRY_ONCE = """
import sys
from aftershock.client import ToolError, tool
def once(name, **a):
    try:
        return tool(name, **a)
    except ToolError as e:
        if e.status < 500:
            raise
        return tool(name, **a)  # one retry only
c = once("lookup_customer", customer="cus_42")
once("charge", customer="cus_42", amount=120)
once("send_email", to=c["email"], subject="Receipt")
once("write_file", path="invoices/cus_42-nov.txt", content="x")
"""


def test_double_sweep_finds_what_single_faults_miss(tmp_path):
    from aftershock.report import only_double, summary
    a = tmp_path / "retry_once.py"
    a.write_text(RETRY_ONCE)
    res = sweep(TASK, [sys.executable, str(a)], ["error"], double=True, max_restarts=0, timeout=20)
    singles = [r for r in res[1:] if len(r.faults) == 1]
    assert singles and all(r.passed for r in singles)
    new = only_double(res)
    assert new and all("unfinished" in kinds_of(r) for r in new)
    assert "only show up when two things break" in summary(res)


def test_cli_run_with_two_faults(capsys):
    code = main(["run", str(DEMO / "invoice.json"), "--fault", "crash-after@2,timeout@4", "--", *agent("safe")])
    assert code == 0
    assert "crash-after at call 2 (charge) then timeout at call 4" in capsys.readouterr().out
