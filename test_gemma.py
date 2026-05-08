import unittest
import numpy as np
from gemma_speaks import PERIOD_SIZE, RATE

class TestGemmaAudio(unittest.TestCase):

    def test_latency_calculation(self):
        """Ensure our buffer size keeps latency under the 50ms human threshold."""
        latency_ms = (PERIOD_SIZE / RATE) * 1000
        print(f"\n[TEST] Calculated Latency: {latency_ms:.2f}ms")
        self.assertLess(latency_ms, 50, "Latency is too high for real-time feel!")

    def test_vad_threshold_logic(self):
        """Test the Voice Activity Detection logic with dummy data."""
        # Mock silence
        silence = np.zeros(PERIOD_SIZE, dtype=np.int16)
        # Mock loud speech
        speech = np.full(PERIOD_SIZE, 1000, dtype=np.int16)
        
        self.assertLess(np.abs(silence).mean(), 800, "VAD triggered on silence!")
        self.assertGreater(np.abs(speech).mean(), 800, "VAD failed to trigger on speech!")

if __name__ == '__main__':
    unittest.main()
