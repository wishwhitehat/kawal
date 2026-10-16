"""Write frontend/.env.production from Terraform outputs.

The values are public client identifiers (the browser API key is restricted to
our domains and Firebase APIs in Terraform), but the file is still git-ignored
so each deployment generates its own.
"""

import json
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[1]


def tf_output(name: str, raw: bool = False) -> str:
    args = ["terraform", f"-chdir={root / 'infra'}", "output", "-raw" if raw else "-json", name]
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


cfg = json.loads(tf_output("firebase_web_config"))
api = tf_output("api_url", raw=True).strip()
target = root / "frontend" / (sys.argv[1] if len(sys.argv) > 1 else ".env.production")
target.write_text(
    f"VITE_API_BASE={api}\n"
    f"VITE_FIREBASE_API_KEY={cfg['apiKey']}\n"
    f"VITE_FIREBASE_AUTH_DOMAIN={cfg['authDomain']}\n"
    f"VITE_FIREBASE_PROJECT_ID={cfg['projectId']}\n"
    f"VITE_FIREBASE_APP_ID={cfg['appId']}\n"
    f"VITE_RECAPTCHA_SITE_KEY={cfg.get('siteKey', '')}\n"
)
print(f"wrote {target.relative_to(root)}")
