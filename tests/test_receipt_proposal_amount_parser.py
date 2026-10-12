# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import shutil
import subprocess
from pathlib import Path

from odoo.tests import TransactionCase

_SCRIPT = Path(__file__).resolve().parent / "amount_parser_test.js"


class TestReceiptProposalAmountParser(TransactionCase):
    """Runs the plain-Node amount parser checks inside the Odoo suite.

    The board's inputs are free text with ``inputmode="decimal"``: an operator
    on a numpad, or with an en_US habit, types ``500.50`` on an es_AR board.
    The old parser dropped every ``.`` and read that as 50050. The parser is a
    pure module, so its cases live in ``amount_parser_test.js`` and execute in
    Node; this test only runs that script and reports its output.

    Node ships in the Odoo image, so a missing Node fails the test: a skip
    would let the suite report green without one parser check having run.
    """

    def test_typed_amounts_are_read_by_locale(self):
        node = shutil.which("node") or shutil.which("nodejs")
        self.assertTrue(
            node, "Node.js is required to run the amount parser checks (not found)."
        )
        result = subprocess.run(
            [node, str(_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        output = f"{result.stdout}\n{result.stderr}"
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("checks passed", result.stdout, output)
