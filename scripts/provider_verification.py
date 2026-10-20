import json
import unittest
from pathlib import Path
loader=unittest.TestLoader()
suite=unittest.TestSuite([loader.discover('tests',pattern='test_provider*.py'),loader.discover('tests',pattern='test_manual_otp.py')])
result=unittest.TextTestRunner(verbosity=2).run(suite)
report={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'live_telegram':False,'live_reloadly':False,'physical_sim':False,'manual_otp':'interface only; NotImplementedError; disabled'}
Path('PROVIDER-VERIFICATION.json').write_text(json.dumps(report,indent=2))
raise SystemExit(0 if result.wasSuccessful() and result.testsRun>=24 else 1)
