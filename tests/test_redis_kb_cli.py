# -*- coding: utf-8 -*-
import io
import sys
import unittest
from contextlib import redirect_stdout

# Module paths
from src.NoSQLKnowledgeBaseConstruction.Redis import query_semantic_kb as kb_cli
from src import main as qmain


class TestRedisSemanticKbCLI(unittest.TestCase):
    def run_cli(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            kb_cli.main(argv)
        return buf.getvalue()

    def test_list_commands_bit_prefix(self):
        out = self.run_cli(["list-commands", "--grep", "^bit"])
        lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
        # Expect at least these commands
        self.assertIn("bitop", lines)
        self.assertIn("bitpos", lines)
        self.assertIn("bitfield", lines)

    def test_show_bitop_args(self):
        out = self.run_cli(["show", "bitop", "--args"])
        self.assertIn("Command: bitop", out)
        self.assertIn("UseSymbol:", out)
        self.assertIn("str_key", out)

    def test_tag2cmd_append(self):
        out = self.run_cli(["tag2cmd", "AppendRule1->elem"]).strip()
        self.assertEqual(out, "append")

    def test_main_delegation(self):
        # Patch argv to go through src.main delegator
        buf = io.StringIO()
        argv_backup = sys.argv[:]
        try:
            sys.argv = ["python", "redis-kb", "list-commands", "--grep", "^bit"]
            with redirect_stdout(buf):
                qmain.main()
        finally:
            sys.argv = argv_backup
        out = buf.getvalue()
        self.assertIn("bitop", out)


if __name__ == "__main__":
    unittest.main()
