import unittest
import numpy as np
import sys
import os

# Add src to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..', 'src')))

from strategies.PairZScore import PairZScoreStrategy

# Mock classes to avoid full dependencies
class MockTradingClient:
    pass

class MockDataClient:
    pass

class TestPairZScoreLogic(unittest.TestCase):
    def setUp(self):
        # Initialize strategy with mock clients
        # We only need to test _compute_zscore, so clients can be empty mocks
        self.strategy = PairZScoreStrategy(
            trading_client=MockTradingClient(),
            data_client=MockDataClient(),
            lookback_window=5,
            z_entry=2.0
        )

    def test_zscore_calculation_insufficient_data(self):
        """Test that z-score is None when not enough data points exist."""
        self.strategy.spreads.clear()
        self.strategy._update_spread(10.0)
        z, mean, std = self.strategy._compute_zscore(10.0)
        self.assertIsNone(z, "Z-score should be None when window is not full")
        self.assertIsNone(mean)
        self.assertIsNone(std)

    def test_zscore_zero_variance(self):
        """Test that z-score handles zero variance (identical values) correctly."""
        self.strategy.spreads.clear()
        # Fill window with constant values
        for _ in range(self.strategy.lookback_window):
            self.strategy._update_spread(50.0)
        
        z, mean, std = self.strategy._compute_zscore(50.0)
        self.assertIsNone(z, "Z-score should be None (or handled) when std dev is 0")
        self.assertEqual(mean, 50.0)
        self.assertEqual(std, 0.0)

    def test_zscore_calculation_fluctuating(self):
        """Test calculation against manual distinct values."""
        self.strategy.spreads.clear()
        spreads = [10.0, 12.0, 10.0, 8.0, 10.0]  # Mean=10, Std=1.414...
        for s in spreads:
            self.strategy._update_spread(s)
            
        # Test a value that should produce a positive z-score
        current_spread_high = 13.0
        z, mean, std = self.strategy._compute_zscore(current_spread_high)
        
        expected_mean = np.mean(spreads)
        expected_std = np.std(spreads, ddof=1)
        expected_z = (current_spread_high - expected_mean) / expected_std
        
        self.assertAlmostEqual(z, expected_z, places=4)
        self.assertAlmostEqual(mean, expected_mean, places=4)
        
        # Test a value that should produce a negative z-score
        current_spread_low = 7.0
        z, mean, std = self.strategy._compute_zscore(current_spread_low)
        expected_z = (current_spread_low - expected_mean) / expected_std
        self.assertAlmostEqual(z, expected_z, places=4)

    def test_entry_exit_signals(self):
        """Verify that z-scores trigger the correct abstract signals (conceptually)."""
        self.strategy.spreads.clear()
        # Setup a stable window first
        spreads = [100.0, 101.0, 99.0, 100.0, 100.0] # Mean ~100, Std ~0.707
        for s in spreads:
            self.strategy._update_spread(s)

        # Case 1: High spread -> Short Signal (Sell A, Buy B)
        high_spread = 105.0 # Z > 2 (approx 7 stds away)
        z, _, _ = self.strategy._compute_zscore(high_spread)
        self.assertTrue(z > self.strategy.z_entry, "Should trigger SHORT spread entry")

        # Case 2: Low spread -> Long Signal (Buy A, Sell B)
        low_spread = 95.0 # Z < -2
        z, _, _ = self.strategy._compute_zscore(low_spread)
        self.assertTrue(z < -self.strategy.z_entry, "Should trigger LONG spread entry")

        # Case 3: Normal spread -> Exit Signal (if in position)
        normal_spread = 100.1 # Z ~ 0
        z, _, _ = self.strategy._compute_zscore(normal_spread)
        self.assertTrue(abs(z) < self.strategy.z_exit, "Should trigger EXIT if in position")

if __name__ == '__main__':
    unittest.main()
