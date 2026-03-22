import subprocess
import json
output = subprocess.run(['python', '-m', 'pyright', 'app.py', '--outputjson'], capture_output=True, text=True)
try:
    data = json.loads(output.stdout)
    with open('results.txt', 'w', encoding='utf-8') as f:
        for err in data.get('generalDiagnostics', []):
            f.write(f"Line {err['range']['start']['line']+1}: {err['message']}\n")
    print("Done")
except Exception as e:
    print(e)
