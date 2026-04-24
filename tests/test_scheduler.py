import os, sys, time, pytest
from shared import PCB, Role, JobType, State, transition_state
from scheduler import submit_job, scheduler_tick, plot_gantt, save_context, load_context, get_context, reset_scheduler, clear_current

def _make_pcb(pid, role=Role.STUDENT, job_type=JobType.PRACTICE, deadline_offset=3600):
    return PCB(pid=pid, user_id=pid*100, role=role, job_type=job_type, deadline=time.time()+deadline_offset, cpu_budget_ns=100)

@pytest.fixture(autouse=True)
def _clean(): reset_scheduler(); yield; reset_scheduler()

def test_exam_preempts_practice():
    p1 = _make_pcb(1, job_type=JobType.PRACTICE, deadline_offset=7200)
    p2 = _make_pcb(2, job_type=JobType.EXAM, deadline_offset=300)
    submit_job(p1); running, _ = scheduler_tick(0)
    assert running.pid == 1
    submit_job(p2); running, preempted = scheduler_tick(1)
    assert running.pid == 2 and preempted.pid == 1 and preempted.state == State.READY

def test_exam_first_in_mixed():
    submit_job(_make_pcb(1, job_type=JobType.PRACTICE, deadline_offset=7200))
    submit_job(_make_pcb(2, role=Role.RESEARCHER, job_type=JobType.RESEARCH, deadline_offset=1800))
    submit_job(_make_pcb(3, job_type=JobType.EXAM, deadline_offset=300))
    running, _ = scheduler_tick(0)
    assert running.pid == 3

def test_tier2_aging():
    r1 = _make_pcb(10, role=Role.RESEARCHER, job_type=JobType.RESEARCH, deadline_offset=1800)
    submit_job(r1); initial = r1.urgency_score
    submit_job(_make_pcb(99, job_type=JobType.EXAM, deadline_offset=300))
    for t in range(6): scheduler_tick(t)
    assert r1.urgency_score >= initial

def test_context_save_restore():
    pcb = _make_pcb(42); save_context(pcb, tick=10)
    assert get_context(pcb) == {"PC": 10, "REG": 20}

def test_context_across_preemption():
    p1 = _make_pcb(1, job_type=JobType.PRACTICE, deadline_offset=7200)
    submit_job(p1); scheduler_tick(0)
    submit_job(_make_pcb(2, job_type=JobType.EXAM, deadline_offset=300))
    _, preempted = scheduler_tick(1)
    assert preempted and "PC" in get_context(preempted)

def test_plot_gantt(tmp_path):
    tl = [(1,"EXAM",0),(1,"EXAM",1),(2,"PRACTICE",2)]
    out = str(tmp_path / "gantt.png"); plot_gantt(tl, path=out)
    assert os.path.isfile(out) and os.path.getsize(out) > 0

def test_30_tick_workload():
    for j in [_make_pcb(1,job_type=JobType.EXAM,deadline_offset=300), _make_pcb(2,job_type=JobType.EXAM,deadline_offset=400),
              _make_pcb(3,job_type=JobType.EXAM,deadline_offset=500), _make_pcb(4,job_type=JobType.PRACTICE,deadline_offset=7200),
              _make_pcb(5,job_type=JobType.PRACTICE,deadline_offset=7200), _make_pcb(6,job_type=JobType.PRACTICE,deadline_offset=7200),
              _make_pcb(7,role=Role.RESEARCHER,job_type=JobType.RESEARCH,deadline_offset=1800),
              _make_pcb(8,role=Role.RESEARCHER,job_type=JobType.RESEARCH,deadline_offset=2000)]:
        submit_job(j)
    tl = []; exam_ticks = 0
    for t in range(30):
        r, _ = scheduler_tick(t)
        if r:
            tl.append((r.pid, r.job_type.name, t))
            if r.job_type == JobType.EXAM: exam_ticks += 1
    assert exam_ticks > 0 and len(tl) == 30

def test_submit_transitions():
    pcb = _make_pcb(99); submit_job(pcb); assert pcb.state == State.READY

def test_evaluation_tier1():
    submit_job(_make_pcb(2, job_type=JobType.PRACTICE, deadline_offset=7200))
    submit_job(_make_pcb(1, role=Role.FACULTY, job_type=JobType.EVALUATION, deadline_offset=600))
    running, _ = scheduler_tick(0)
    assert running.pid == 1

def test_clear_current_allows_next_job():
    submit_job(_make_pcb(1, job_type=JobType.EXAM, deadline_offset=300))
    submit_job(_make_pcb(2, job_type=JobType.PRACTICE, deadline_offset=7200))
    r, _ = scheduler_tick(0); assert r.pid == 1
    # Simulate job exit
    transition_state(r, State.EXIT); clear_current()
    r2, _ = scheduler_tick(1)
    assert r2 is not None and r2.pid == 2