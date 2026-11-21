"""Entry point used inside the sandbox container: `python -m trop.capture.worker <url> --out /out`."""
import sys

from .capture import main

sys.exit(main())
