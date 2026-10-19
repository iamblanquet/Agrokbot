"""Exercise deployment control flow with fake Docker, never a daemon or production."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class DeploySafetyTests(unittest.TestCase):
    def simulate(self, failure=''):
        git_bash=Path('C:/Program Files/Git/bin/bash.exe')
        bash=str(git_bash) if git_bash.exists() else shutil.which('bash')
        if not bash:self.skipTest('Bash not available')
        script=(Path(__file__).resolve().parents[1]/'deploy/activate-release.sh').read_text(encoding='utf-8')
        script=script.replace('cd /home/mblanquet/Agrokbot','cd "$TEST_WORKSPACE"').replace('/var/lock/campo-deploy.lock','deploy.lock').replace('/home/mblanquet/campo-backups/','backups/')
        mocks='''
node() { echo node-tests >> calls; [ "$TEST_FAILURE" != tests ]; }
flock() { return 0; }
git() { echo abc1234; }
docker() {
  echo "docker $* image=$CAMPO_IMAGE" >> calls
  case "$*" in
    *"ps -q campo"*) echo old-container ;;
    "inspect "*) echo old-image ;;
    "run "*) [ "$TEST_FAILURE" != backend ] || return 1 ;;
    *"up -d"*) if [ "$TEST_FAILURE" = activation ] && [ -z "$CAMPO_IMAGE" ]; then return 1; fi ;;
  esac
  return 0
}
'''
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'.env').write_text('TEST_ONLY=true',encoding='utf-8')
            env={**os.environ,'TEST_WORKSPACE':Path(directory).as_posix(),'TEST_FAILURE':failure,'CAMPO_IMAGE':''}
            result=subprocess.run([bash,'--noprofile','--norc'],input=mocks+script,text=True,encoding='utf-8',capture_output=True,env=env,timeout=30)
            calls=Path(directory,'calls').read_text() if Path(directory,'calls').exists() else ''
        return result,calls

    def test_frontend_failure_never_activates(self):
        result,calls=self.simulate('tests')
        self.assertNotEqual(result.returncode,0,result.stderr)
        self.assertNotIn('up -d',calls)

    def test_backend_failure_never_backs_up_or_activates(self):
        result,calls=self.simulate('backend')
        self.assertNotEqual(result.returncode,0,result.stderr)
        self.assertNotIn('up -d',calls)
        self.assertNotIn('sqlite3',calls)

    def test_backup_precedes_activation_and_failed_activation_rolls_back(self):
        result,calls=self.simulate('activation')
        self.assertNotEqual(result.returncode,0,result.stderr)
        self.assertIn('s.backup(d)',calls,result.stderr)
        self.assertLess(calls.index('s.backup(d)'),calls.index('up -d'))
        self.assertIn('--no-build',calls,result.stderr)
        self.assertIn('image=agrokbot-campo:rollback-',calls,result.stderr)
        self.assertNotIn('cleanup',calls)

    def test_success_does_not_delete_backups_or_rollback_image(self):
        result,calls=self.simulate()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('s.backup(d)',calls)
        self.assertNotIn('image rm',calls)
        self.assertNotIn('cleanup',calls)
