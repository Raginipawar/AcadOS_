import time, pytest, os
from shared import PCB, Role, JobType, State, transition_state, load_pcb_from_c

def test_pcb_creation():
    pcb = PCB(pid=10, user_id=999, role=Role.RESEARCHER, job_type=JobType.RESEARCH, deadline=time.time()+3600, cpu_budget_ns=1000000)
    assert pcb.pid == 10 and pcb.role == Role.RESEARCHER and pcb.state == State.NEW

def test_compute_urgency():
    now = time.time()
    e = PCB(pid=1, user_id=1, role=Role.STUDENT, job_type=JobType.EXAM, deadline=now+100, cpu_budget_ns=100)
    p = PCB(pid=2, user_id=2, role=Role.STUDENT, job_type=JobType.PRACTICE, deadline=now+100, cpu_budget_ns=100)
    assert e.compute_urgency() > p.compute_urgency()

def test_legal_transitions():
    pcb = PCB(pid=1, user_id=1, role=Role.STUDENT, job_type=JobType.EXAM, deadline=time.time()+100, cpu_budget_ns=100)
    transition_state(pcb, State.READY); assert pcb.state == State.READY
    transition_state(pcb, State.RUNNING); assert pcb.state == State.RUNNING
    transition_state(pcb, State.BLOCKED); assert pcb.state == State.BLOCKED

def test_illegal_transitions():
    pcb = PCB(pid=1, user_id=1, role=Role.STUDENT, job_type=JobType.EXAM, deadline=time.time()+100, cpu_budget_ns=100)
    with pytest.raises(ValueError): transition_state(pcb, State.RUNNING)
    transition_state(pcb, State.READY); transition_state(pcb, State.RUNNING)
    with pytest.raises(ValueError): transition_state(pcb, State.NEW)