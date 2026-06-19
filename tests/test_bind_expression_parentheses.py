import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import formula_registry


class BindExpressionParenthesesTests(unittest.TestCase):
    def test_binder_does_not_add_implicit_parentheses(self):
        with patch.object(
            formula_registry,
            "get_formula",
            return_value={"canonical_sympy_expr": "-{Fox}"},
        ):
            self.assertEqual(formula_registry.bind_expression("test.raw", Fox="a+b"), "-a+b")

    def test_registry_templates_carry_required_parentheses_explicitly(self):
        expression = formula_registry.bind_expression("common.adapter.a-c", Fc="a+b")
        self.assertEqual(expression, "(s*L+rL)*(a+b)/Vg")


if __name__ == "__main__":
    unittest.main()
