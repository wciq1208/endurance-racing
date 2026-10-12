import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'.agents/skills/z24-race-manager/scripts'))
import race_process as rp
import portalocker


class ProcessTests(unittest.TestCase):
    def test_platform_launch_flags(self):
        self.assertEqual(rp.detached_options('nt'), {'creationflags': 0x208})
        self.assertEqual(rp.detached_options('posix'), {'start_new_session': True})

    def test_exact_script_and_token_with_spaces(self):
        script = Path(tempfile.gettempdir())/'a b'/'worker.py'
        self.assertTrue(rp.matches(['python', str(script), '--token', 'abc'], 'abc', [script]))
        self.assertFalse(rp.matches(['python', str(script), '--token', 'abcdef'], 'abc', [script]))
        self.assertFalse(rp.matches(['python', str(script.parent/'other.py'), '--token', 'abc'], 'abc', [script]))
        self.assertFalse(rp.matches(['python', '-c', str(script), '--token', 'abc'], 'abc', [script]))

    def test_stops_children_and_preserves_other_run(self):
        with tempfile.TemporaryDirectory(prefix='race space ') as temp:
            script = Path(temp)/'worker.py'
            child_pid = Path(temp)/'child.pid'
            script.write_text("""import subprocess,sys,time
from pathlib import Path
if '--parent' in sys.argv:
    child=subprocess.Popen([sys.executable,__file__,'--token',sys.argv[sys.argv.index('--token')+1]])
    Path(sys.argv[-1]).write_text(str(child.pid))
time.sleep(90)
""", encoding='utf-8')
            token = uuid.uuid4().hex
            parent = subprocess.Popen([sys.executable, str(script), '--token', token, '--parent', str(child_pid)], **rp.detached_options())
            other = subprocess.Popen([sys.executable, str(script), '--token', token+'other'], **rp.detached_options())
            try:
                deadline = time.monotonic()+10
                while not child_pid.exists() and time.monotonic()<deadline:
                    time.sleep(.05)
                self.assertTrue(child_pid.exists())
                self.assertGreaterEqual(len(rp.owned_processes({'token':token}, [script])), 2)
                self.assertTrue(rp.stop_owned({'pid':parent.pid,'token':token}, [script]))
                self.assertFalse(rp.owned_processes({'token':token}, [script]))
                self.assertIsNone(other.poll())
            finally:
                rp.stop_owned({'token':token}, [script])
                other.kill();other.wait()
                if parent.poll() is None:parent.kill()
                parent.wait()

    def test_file_lock_excludes_another_process(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'test.lock'
            with path.open('a') as handle:
                portalocker.lock(handle, portalocker.LOCK_EX)
                code="import portalocker,sys; f=open(sys.argv[1],'a'); portalocker.lock(f,portalocker.LOCK_EX|portalocker.LOCK_NB)"
                result=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True)
                self.assertNotEqual(result.returncode,0)
            result=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
