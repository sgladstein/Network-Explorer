from network_explorer.wifi import band_for_frequency, channel_for_frequency, normalize_bssid, normalize_ssid, signal_grade


def test_bands_and_channels():
    assert (band_for_frequency(2412), channel_for_frequency(2412)) == ("2.4", 1)
    assert channel_for_frequency(2484) == 14
    assert (band_for_frequency(5180), channel_for_frequency(5180)) == ("5", 36)
    assert (band_for_frequency(5745), channel_for_frequency(5745)) == ("5", 149)
    assert (band_for_frequency(5955), channel_for_frequency(5955)) == ("6", 1)
    assert band_for_frequency(None) is None and channel_for_frequency(900) is None


def test_signal_grade():
    assert signal_grade(-55) == "excellent"
    assert signal_grade(-65) == "good"
    assert signal_grade(-72) == "fair"
    assert signal_grade(-80) == "poor"
    assert signal_grade(None) == "unknown"


def test_normalizers():
    assert normalize_bssid("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"
    assert normalize_bssid("02:00:00:00:00:00") is None
    assert normalize_ssid('"Home"') == "Home"
    assert normalize_ssid("<unknown ssid>") is None
