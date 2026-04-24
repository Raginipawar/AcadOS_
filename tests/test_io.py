import pytest, sqlite3, os, time
from shared import PCB, Role, JobType, State
from io_manager import cscan, sstf, create_db, log_job, AbuseMonitor

def test_cscan():
    assert cscan([95,180,34,119,11,123,62,64,66], 50) == [62,64,66,95,119,123,180,11,34]

def test_sstf():
    assert sstf([95,180,34,119,11,123,62,64,66], 50) == [62,64,66,95,119,123,180,34,11]

def test_log_job():
    if os.path.exists('acados.db'): os.remove('acados.db')
    create_db()
    pcb = PCB(pid=999, user_id=1, role=Role.STUDENT, job_type=JobType.EXAM, deadline=time.time()+1000, cpu_budget_ns=500, cpu_used=600)
    log_job(pcb)
    conn = sqlite3.connect('acados.db'); row = conn.cursor().execute("SELECT * FROM job_log WHERE pid=999").fetchone(); conn.close()
    assert row is not None and row[0] == 999

def test_abuse_monitor():
    pcb = PCB(pid=1001, user_id=2, role=Role.STUDENT, job_type=JobType.PRACTICE, deadline=time.time()+1000, cpu_budget_ns=100, cpu_used=250, state=State.RUNNING)
    monitor = AbuseMonitor([pcb], tick_interval=0.1); monitor.start()
    time.sleep(0.3); monitor.stop(); monitor.join()
    assert pcb.abuse_flag is True and pcb.state == State.THROTTLED