import runpy
import os
import sys
import tempfile
import uuid
tempfile.tempdir = 'F:\\ppt-skill\\ppt-template-generator\\projects\\intake_20260706\\output\\fund-pension-annuity-step3b-draft-render-tmp'
class _NoCleanupTemporaryDirectory:
    def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False):
        base = dir or tempfile.tempdir
        name = (prefix or 'tmp') + uuid.uuid4().hex + (suffix or '')
        self.name = os.path.join(base, name)
        os.makedirs(self.name, exist_ok=False)
        os.chmod(self.name, 0o777)
    def __enter__(self):
        return self.name
    def __exit__(self, exc_type, exc, tb):
        return False
    def cleanup(self):
        return None
tempfile.TemporaryDirectory = _NoCleanupTemporaryDirectory
sys.argv = ['C:\\Users\\xiaojian\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.630.12135\\skills\\presentations\\container_tools\\render_slides.py'] + sys.argv[1:]
runpy.run_path('C:\\Users\\xiaojian\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.630.12135\\skills\\presentations\\container_tools\\render_slides.py', run_name='__main__')
