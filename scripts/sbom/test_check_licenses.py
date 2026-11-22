import unittest

from check_licenses import allowed_expr


class LicenseExpressionTests(unittest.TestCase):
    def test_and_operand_order_does_not_change_or_result(self):
        left_first = "(GPL-3.0-only AND MIT) OR Apache-2.0"
        right_first = "(MIT AND GPL-3.0-only) OR Apache-2.0"
        self.assertTrue(allowed_expr(left_first))
        self.assertEqual(allowed_expr(left_first), allowed_expr(right_first))

    def test_both_orders_of_copyleft_and_are_blocked_without_alternative(self):
        self.assertFalse(allowed_expr("GPL-3.0-only AND MIT"))
        self.assertFalse(allowed_expr("MIT AND GPL-3.0-only"))


if __name__ == "__main__":
    unittest.main()
