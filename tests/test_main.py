import unittest

from main import is_target_role, process_jobs


class MainTests(unittest.TestCase):
    def test_is_target_role_matches_aerospace_keywords(self):
        self.assertTrue(is_target_role("Internship - Guidance, Navigation and Control"))
        self.assertTrue(is_target_role("Aerospace Flight Software Co-op"))

    def test_is_target_role_rejects_non_matching_roles(self):
        self.assertFalse(is_target_role("Software Engineer - Backend"))
        self.assertFalse(is_target_role("Marketing Internship"))

    def test_process_jobs_only_returns_new_matches(self):
        jobs = [
            {"id": "1", "title": "Aerospace Flight Software Co-op", "location": "Los Angeles", "url": "https://example.com/1"},
            {"id": "2", "title": "Rocket Propulsion Intern", "location": "Seattle", "url": "https://example.com/2"},
            {"id": "1", "title": "Aerospace Flight Software Co-op", "location": "Los Angeles", "url": "https://example.com/1"},
        ]

        seen = set()
        matches = process_jobs(jobs, seen)

        self.assertEqual(len(matches), 2)
        self.assertEqual(seen, {"1", "2"})


if __name__ == "__main__":
    unittest.main()
