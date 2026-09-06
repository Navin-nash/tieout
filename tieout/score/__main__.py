"""``python -m tieout.score`` -- the out-of-process scorer entry point."""

import sys

from tieout.score.run import main

if __name__ == "__main__":
    sys.exit(main())
