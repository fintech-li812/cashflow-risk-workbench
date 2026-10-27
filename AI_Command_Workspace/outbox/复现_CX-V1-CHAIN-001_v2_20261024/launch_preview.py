"""Compatibility entry point; QA checks and approved hash live in qa_entry.py."""
import sys
from qa_entry import main
if __name__=='__main__':
    sys.argv=[sys.argv[0],'web']
    main()
