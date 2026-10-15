import unittest

from gui.error_messages import TRIAL_QUOTA_EXHAUSTED_MESSAGE, friendly_runtime_error


class ErrorMessageTests(unittest.TestCase):
    def test_quota_exhausted_uses_trial_quota_message(self) -> None:
        raw = (
            "game s2t websocket receive failed: received 1008 "
            "(policy violation) quota_exhausted"
        )

        self.assertEqual(friendly_runtime_error(raw), TRIAL_QUOTA_EXHAUSTED_MESSAGE)

    def test_logged_quota_exhausted_uses_trial_quota_message(self) -> None:
        raw = (
            "Error: websocket receive failed: received 1008 "
            "(policy violation) quota_exhausted; then sent 1008 "
            "(policy violation) quota_exhausted"
        )

        self.assertEqual(friendly_runtime_error(raw), TRIAL_QUOTA_EXHAUSTED_MESSAGE)

    def test_other_errors_are_left_unchanged(self) -> None:
        raw = "game s2t websocket receive failed: connection reset"

        self.assertEqual(friendly_runtime_error(raw), raw)


if __name__ == "__main__":
    unittest.main()
