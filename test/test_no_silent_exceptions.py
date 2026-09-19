"""Every except handler must log, re-raise, or say why it is silent.

A handler that swallows an error without a trace turns a production failure into a
guess (issue #68: the LCU session handler hid every exception behind `except: pass`).
A handler that is silent on purpose documents it on the except line:

    except queue.Empty:  # silent-ok: queue drained

Anything else fails this test with the file, line and function to fix.
"""

import ast
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = (".claude/", "vendor/", "test/", "testes_Pesados/", "relay-worker/", "skin-key-worker/",
                 "scripts/", "build/", "dist/")
LOG_CALLS = {"debug", "info", "warning", "error", "exception", "critical",
             "log_event", "log_status", "log_section", "print"}
MARKER = "silent-ok"


def _project_files():
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    return [ROOT / p for p in out.splitlines() if p and not p.startswith(EXCLUDED_DIRS)]


def _reports(body):
    for node in body:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Raise):
                return True
            if isinstance(sub, ast.Call):
                func = sub.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name in LOG_CALLS:
                    return True
    return False


def find_silent_handlers(path):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ExceptHandler) and not _reports(node.body):
            if MARKER not in lines[node.lineno - 1]:
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}: "
                                 f"{lines[node.lineno - 1].strip()}")
    return offenders


class NoSilentExceptionsTests(unittest.TestCase):
    def test_every_handler_logs_or_documents_its_silence(self):
        offenders = [o for path in _project_files() for o in find_silent_handlers(path)]
        self.assertEqual(
            offenders, [],
            "Silent except handlers: add a log call, re-raise, or append "
            f"'# {MARKER}: <reason>' to the except line:\n" + "\n".join(offenders),
        )

    def test_detector_flags_a_bare_pass(self):
        sample = ROOT / "test" / "_silent_sample.py"
        sample.write_text("try:\n    x = 1\nexcept Exception:\n    pass\n", encoding="utf-8")
        self.addCleanup(sample.unlink)
        self.assertEqual(len(find_silent_handlers(sample)), 1)

    def test_detector_accepts_log_and_marker(self):
        sample = ROOT / "test" / "_silent_sample_ok.py"
        sample.write_text(
            "try:\n    x = 1\nexcept ValueError:  # silent-ok: expected\n    pass\n"
            "try:\n    x = 2\nexcept OSError as e:\n    log.debug(e)\n",
            encoding="utf-8",
        )
        self.addCleanup(sample.unlink)
        self.assertEqual(find_silent_handlers(sample), [])


if __name__ == "__main__":
    unittest.main()
