import sys

sys.path.append("/opt/quex-v1-signer")

import waitress.runner

waitress.runner.run(["/bin/waitress-serve", "--call", "quex_backend:create_app"]);
