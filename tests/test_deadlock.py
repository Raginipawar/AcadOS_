import time, threading, pytest
from shared import PCB, Role, JobType, State
from deadlock import ResourceManager, create_db, db_read, db_write

def make_pcb(pid, job_type=JobType.PRACTICE, role=Role.STUDENT):
    return PCB(pid=pid, user_id=pid*10, role=role, job_type=job_type, deadline=time.time()+3600, cpu_budget_ns=1000000)

def test_safe_request():
    rm = ResourceManager(); pcb = make_pcb(1); rm.register(pcb, {'CPU':2,'MEM_BLOCK':4})
    assert rm.request_resources(pcb, {'CPU':1,'MEM_BLOCK':2}) is True

def test_unsafe_request():
    rm = ResourceManager(); rm.available = {'CPU':1,'MEM_BLOCK':1}
    for p in [make_pcb(i) for i in range(1,4)]:
        rm.max_need[p.pid] = {'CPU':3,'MEM_BLOCK':3}; rm.allocation[p.pid] = {'CPU':1,'MEM_BLOCK':1}
    assert rm.request_resources(make_pcb(1), {'CPU':1,'MEM_BLOCK':1}) is False

def test_recovery_order():
    rm = ResourceManager(); rm.available = {'CPU':0,'MEM_BLOCK':0}
    exam = make_pcb(1, JobType.EXAM); research = make_pcb(2, JobType.RESEARCH); practice = make_pcb(3, JobType.PRACTICE)
    for pid, alloc in [(1,2),(2,1),(3,1)]:
        rm.max_need[pid] = {'CPU':3,'MEM_BLOCK':3}; rm.allocation[pid] = {'CPU':alloc,'MEM_BLOCK':alloc}
    terminated = rm.deadlock_recover([exam, research, practice])
    assert terminated[0] == 3 and 1 not in terminated

def test_readers_writers():
    create_db()
    db_write(777, {'user_id':1,'role':'STUDENT','job_type':'PRACTICE','cpu_used':0,'start_time':0.0,'end_time':0.0,'missed_deadline':0})
    results, errors = [], []
    def reader():
        try: results.append(db_read(777))
        except Exception as e: errors.append(str(e))
    threads = [threading.Thread(target=reader) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=10)
    assert not errors and len(results) == 5

def test_release():
    rm = ResourceManager(); pcb = make_pcb(1); rm.register(pcb, {'CPU':2,'MEM_BLOCK':4})
    rm.request_resources(pcb, {'CPU':1,'MEM_BLOCK':3})
    cpu_before = rm.available['CPU']; rm.release_resources(pcb)
    assert rm.available['CPU'] == cpu_before + 1 and 1 not in rm.allocation