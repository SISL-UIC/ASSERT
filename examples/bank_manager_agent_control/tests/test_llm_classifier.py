"""Gate (Direction 1) — learned-classifier parse + fail-safe + band logic.

The classifier is an LLM, but its score→decision mapping and its failure
behavior must be deterministic and safe: any error escalates to a human, never
silently allows. The Rego gate ordering (typed gates first, learned gate last)
is covered in test_policy.py.
"""

import _bootstrap  # noqa: F401

import unittest
from unittest import mock

import llm_classifier as lc


class ClassifierBands(unittest.TestCase):
    def test_snapshot_carries_thresholds_and_score(self):
        with mock.patch.object(lc, "score_transcript", return_value=10):
            snap = lc.classifier_snapshot("hi", "read_account", {"account_id": "ACC-1001"})
        self.assertEqual(snap["llm_risk_score"], 10)
        self.assertEqual(snap["llm_escalate_lo"], lc.DEFAULT_ESCALATE_LO)
        self.assertEqual(snap["llm_deny_hi"], lc.DEFAULT_DENY_HI)

    def test_failsafe_score_is_in_escalate_band(self):
        # On API/parse error, score_transcript returns a value that ESCALATES,
        # i.e. strictly above escalate_lo and at-or-below deny_hi (never allow).
        self.assertGreater(lc._FAILSAFE_SCORE, lc.DEFAULT_ESCALATE_LO)
        self.assertLessEqual(lc._FAILSAFE_SCORE, lc.DEFAULT_DENY_HI)

    def test_shim_wrapper_failsafe_in_escalate_band(self):
        # If the post_enrich classifier wrapper crashes, acs_shim injects a score
        # that must ESCALATE (never allow): strictly above escalate_lo, at/below deny_hi.
        import acs_shim
        self.assertGreater(acs_shim.WRAPPER_FAILSAFE_SCORE, lc.DEFAULT_ESCALATE_LO)
        self.assertLessEqual(acs_shim.WRAPPER_FAILSAFE_SCORE, lc.DEFAULT_DENY_HI)

    def test_api_error_yields_failsafe(self):
        with mock.patch.dict("os.environ", {"AZURE_API_KEY": "k", "AZURE_API_BASE": "b"}):
            with mock.patch("openai.AzureOpenAI", side_effect=RuntimeError("boom")):
                self.assertEqual(lc.score_transcript("x", "create_transfer", {}), lc._FAILSAFE_SCORE)

    def test_parses_integer_from_reply(self):
        fake = mock.MagicMock()
        fake.chat.completions.create.return_value.choices = [
            mock.MagicMock(message=mock.MagicMock(content="87"))]
        with mock.patch.dict("os.environ", {"AZURE_API_KEY": "k", "AZURE_API_BASE": "b", "AGENT_MODEL": "gpt-5.4-mini"}):
            with mock.patch("openai.AzureOpenAI", return_value=fake):
                self.assertEqual(lc.score_transcript("coerce", "create_transfer", {}), 87)

    def test_non_numeric_reply_failsafe(self):
        fake = mock.MagicMock()
        fake.chat.completions.create.return_value.choices = [
            mock.MagicMock(message=mock.MagicMock(content="no idea"))]
        with mock.patch.dict("os.environ", {"AZURE_API_KEY": "k", "AZURE_API_BASE": "b", "AGENT_MODEL": "gpt-5.4-mini"}):
            with mock.patch("openai.AzureOpenAI", return_value=fake):
                self.assertEqual(lc.score_transcript("x", "create_transfer", {}), lc._FAILSAFE_SCORE)

    def test_score_clamped(self):
        fake = mock.MagicMock()
        fake.chat.completions.create.return_value.choices = [
            mock.MagicMock(message=mock.MagicMock(content="250"))]
        with mock.patch.dict("os.environ", {"AZURE_API_KEY": "k", "AZURE_API_BASE": "b", "AGENT_MODEL": "gpt-5.4-mini"}):
            with mock.patch("openai.AzureOpenAI", return_value=fake):
                self.assertEqual(lc.score_transcript("x", "create_transfer", {}), 100)


class DiscriminationGuard(unittest.TestCase):
    """The pre-flight that catches a throttled/fail-safed (constant) classifier."""

    def test_clear_separation_passes(self):
        with mock.patch.object(lc, "score_transcript", side_effect=[95, 5]):
            ok, c, b = lc.discrimination_ok()
        self.assertTrue(ok)
        self.assertEqual((c, b), (95, 5))

    def test_collapsed_to_failsafe_fails(self):
        # Both coercive and benign collapse to the fail-safe band (throttled): a
        # constant classifier must NOT pass the discrimination guard.
        fs = lc._FAILSAFE_SCORE
        with mock.patch.object(lc, "score_transcript", side_effect=[fs, fs]):
            ok, c, b = lc.discrimination_ok()
        self.assertFalse(ok)

    def test_narrow_gap_fails(self):
        with mock.patch.object(lc, "score_transcript", side_effect=[72, 40]):
            ok, _c, _b = lc.discrimination_ok()
        self.assertFalse(ok)  # gap < 50 and benign > 30


if __name__ == "__main__":
    unittest.main()
