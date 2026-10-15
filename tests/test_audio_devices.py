import unittest

from app_core.audio_devices import AudioDevice, is_virtual_loopback_input


class AudioDeviceTests(unittest.TestCase):
    def test_detects_virtual_loopback_recording_endpoints(self) -> None:
        self.assertTrue(
            is_virtual_loopback_input(AudioDevice(1, "CABLE Output (VB-Audio Virtual Cable)", "MME", 1, 0, 48000))
        )
        self.assertTrue(
            is_virtual_loopback_input(AudioDevice(2, "Voicemeeter AUX Output (VB-Audio Voicemeeter AUX VAIO)", "MME", 8, 0, 48000))
        )
        self.assertTrue(
            is_virtual_loopback_input(AudioDevice(3, "Stereo Mix (Realtek Audio)", "Windows WASAPI", 2, 0, 48000))
        )
        self.assertFalse(is_virtual_loopback_input(AudioDevice(4, "Microphone Array (Realtek Audio)", "MME", 2, 0, 48000)))


if __name__ == "__main__":
    unittest.main()
