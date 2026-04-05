"""Unit tests for AnkiGuidGenerator."""

import pytest

from ankify.anki.anki_deck_creator import AnkiGuidGenerator


class TestAnkiGuidGenerator:
    """Tests for AnkiGuidGenerator static methods."""

    def test_random_int_guid_is_positive(self):
        """random_int_guid returns a positive integer."""
        for _ in range(5):
            guid = AnkiGuidGenerator.random_int_guid()
            assert guid > 0

    def test_random_int_guid_is_within_64bit_range(self):
        """random_int_guid returns value within signed 64-bit range."""
        max_val = (1 << 63) - 1
        for _ in range(5):
            guid = AnkiGuidGenerator.random_int_guid()
            assert 1 <= guid <= max_val

    def test_random_int_guid_is_random(self):
        """random_int_guid returns different values on each call."""
        guids = [AnkiGuidGenerator.random_int_guid() for _ in range(5)]
        assert len(set(guids)) == 5

    def test_random_base91_guid_is_string(self):
        """random_base91_guid returns a string."""
        guid = AnkiGuidGenerator.random_base91_guid()
        assert isinstance(guid, str)
        assert len(guid) > 0

    def test_random_base91_guid_uses_valid_alphabet(self):
        """random_base91_guid uses only characters from Anki base91 alphabet."""
        valid_chars = set(AnkiGuidGenerator._ANKI_BASE91_TABLE)
        for _ in range(5):
            guid = AnkiGuidGenerator.random_base91_guid()
            for char in guid:
                assert char in valid_chars, f"Invalid character '{char}' in GUID"

    def test_hash_based_int_guid_is_deterministic(self):
        """hash_based_int_guid returns same value for same input."""
        data = "test_data"
        guid1 = AnkiGuidGenerator.hash_based_int_guid(data)
        guid2 = AnkiGuidGenerator.hash_based_int_guid(data)
        assert guid1 == guid2

    def test_hash_based_int_guid_different_for_different_input(self):
        """hash_based_int_guid returns different values for different inputs."""
        guid1 = AnkiGuidGenerator.hash_based_int_guid("data1")
        guid2 = AnkiGuidGenerator.hash_based_int_guid("data2")
        assert guid1 != guid2

    def test_hash_based_int_guid_is_positive(self):
        """hash_based_int_guid returns positive integer."""
        test_inputs = ["", "a", "test", "Ankify Basic", "very_long_string" * 100]
        for data in test_inputs:
            guid = AnkiGuidGenerator.hash_based_int_guid(data)
            assert guid > 0

    def test_hash_based_int_guid_is_within_64bit_range(self):
        """hash_based_int_guid returns value within signed 64-bit range."""
        max_val = (1 << 63) - 1
        test_inputs = ["test1", "test2", "unicode: Привет", "emoji: 😀"]
        for data in test_inputs:
            guid = AnkiGuidGenerator.hash_based_int_guid(data)
            assert 1 <= guid <= max_val

    def test_hash_based_base91_guid_is_deterministic(self):
        """hash_based_base91_guid returns same value for same input."""
        data = "test_model_name"
        guid1 = AnkiGuidGenerator.hash_based_base91_guid(data)
        guid2 = AnkiGuidGenerator.hash_based_base91_guid(data)
        assert guid1 == guid2

    def test_hash_based_base91_guid_uses_valid_alphabet(self):
        """hash_based_base91_guid uses only characters from Anki base91 alphabet."""
        valid_chars = set(AnkiGuidGenerator._ANKI_BASE91_TABLE)
        test_inputs = ["model1", "model2", "Ankify Basic"]
        for data in test_inputs:
            guid = AnkiGuidGenerator.hash_based_base91_guid(data)
            for char in guid:
                assert char in valid_chars

    def test_encode_base91_small_values(self):
        """_encode_base91 correctly encodes small values."""
        # Value 0 should raise
        with pytest.raises(ValueError):
            AnkiGuidGenerator._encode_base91(0)

        # Value 1 should be first character
        assert AnkiGuidGenerator._encode_base91(1) == "b"  # 1 mod 91 = 1, table[1] = 'b'

        # Value equal to base (91) should be "ba"
        assert AnkiGuidGenerator._encode_base91(91) == "ba"

    def test_encode_base91_negative_raises(self):
        """_encode_base91 raises ValueError for negative values."""
        with pytest.raises(ValueError, match="positive"):
            AnkiGuidGenerator._encode_base91(-1)

    def test_base91_alphabet_has_91_chars(self):
        """The base91 alphabet has exactly 91 characters."""
        assert len(AnkiGuidGenerator._ANKI_BASE91_TABLE) == 91

    def test_base91_alphabet_no_duplicates(self):
        """The base91 alphabet has no duplicate characters."""
        chars = AnkiGuidGenerator._ANKI_BASE91_TABLE
        assert len(chars) == len(set(chars))
