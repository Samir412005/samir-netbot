import json, pathlib, xml.etree.ElementTree as ET
files = list(pathlib.Path('app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
assert files, 'Missing unit test XML evidence'
suites = [ET.parse(f).getroot() for f in files]
count = sum(int(s.attrib['tests']) for s in suites)
failures = sum(int(s.attrib.get('failures', 0)) + int(s.attrib.get('errors', 0)) for s in suites)
assert count >= 7 and failures == 0
report = {'version': '0.3.0-preview3', 'tests': count, 'failures': failures,
          'cases': [c.attrib['name'] for s in suites for c in s.findall('testcase')],
          'telegram': 'MockWebServer only; no live bot token used',
          'ussd': 'Real Android TelephonyManager API implemented; physical SIM not tested'}
pathlib.Path('VERIFICATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
