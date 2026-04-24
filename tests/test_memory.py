import pytest
from memory import MemoryManager
from shared import PCB, Role, JobType

def test_tlb_hit():
    mm = MemoryManager()
    pcb = PCB(pid=1, user_id=100, role=Role.STUDENT, job_type=JobType.PRACTICE, deadline=1000.0, cpu_budget_ns=1000000)
    f1 = mm.access_page(pcb, 0, tick=1); faults1 = mm.fault_counters.get('PRACTICE', 0)
    f2 = mm.access_page(pcb, 0, tick=2); faults2 = mm.fault_counters.get('PRACTICE', 0)
    assert faults2 == faults1 and f1 == f2

def test_page_fault():
    mm = MemoryManager()
    pcb = PCB(pid=2, user_id=101, role=Role.STUDENT, job_type=JobType.RESEARCH, deadline=2000.0, cpu_budget_ns=2000000)
    mm.access_page(pcb, 5, tick=1)
    assert mm.fault_counters.get('RESEARCH', 0) == 1 and 5 in mm.page_table[pcb.pid]

def test_exam_not_evicted():
    mm = MemoryManager()
    for i in range(8):
        pcb = PCB(pid=100+i, user_id=200+i, role=Role.STUDENT, job_type=JobType.PRACTICE, deadline=3000.0, cpu_budget_ns=1000000)
        mm.allocate_pages(pcb, 4)
        for v in range(4): mm.access_page(pcb, v, tick=i*4+v+1)
    exam = PCB(pid=500, user_id=600, role=Role.FACULTY, job_type=JobType.EXAM, deadline=4000.0, cpu_budget_ns=5000000)
    mm.allocate_pages(exam, 4)
    assert exam.pid in mm.page_table and len(mm.page_table[exam.pid]) == 4

def test_free_pages():
    mm = MemoryManager()
    pcb = PCB(pid=10, user_id=110, role=Role.RESEARCHER, job_type=JobType.RESEARCH, deadline=6000.0, cpu_budget_ns=3000000)
    init = len(mm.free_frames); mm.allocate_pages(pcb, 8)
    for v in range(4): mm.access_page(pcb, v, tick=v+1)
    mm.free_pages(pcb)
    assert len(mm.free_frames) == init and pcb.pid not in mm.page_table