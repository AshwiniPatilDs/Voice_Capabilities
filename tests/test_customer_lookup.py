import unittest

from customer_lookup import (
    build_customer_lookup_system_message,
    lookup_customer_details,
    normalize_lookup_key,
)


class CustomerLookupTests(unittest.TestCase):
    def test_normalizes_common_lookup_keys(self) -> None:
        self.assertEqual(normalize_lookup_key("Policy No"), "policy_no")
        self.assertEqual(normalize_lookup_key("contact number"), "contact_no")
        self.assertEqual(normalize_lookup_key("customer name"), "policy_holder_name")

    def test_looks_up_customer_by_policy_number(self) -> None:
        record = lookup_customer_details("policy_no", "PRL-1001")
        self.assertIsNotNone(record)
        self.assertEqual(record["policy_holder_name"], "Amit Sharma")

    def test_looks_up_customer_by_contact_number(self) -> None:
        record = lookup_customer_details("contact_no", "9876543210")
        self.assertIsNotNone(record)
        self.assertEqual(record["policy_no"], "PRL-1001")

    def test_builds_customer_lookup_system_message(self) -> None:
        prompt = build_customer_lookup_system_message("You are a helpful support agent.")
        self.assertIn("You are a helpful support agent.", prompt)
        self.assertIn("LOCAL CUSTOMER DATABASE FOR LOOKUP", prompt)
        self.assertIn("PRL-1001", prompt)
        self.assertIn("policy_no", prompt)


if __name__ == "__main__":
    unittest.main()
