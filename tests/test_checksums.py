import hashlib
from pathlib import Path

from installer.checksums import ChecksumMismatch, expected_sha256, sha256_file

RG = "ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
HASH_A = "a" * 64
HASH_B = "b" * 64


def test_multiline_checksums_file_finds_asset_hash():
    text = f"{HASH_A}  other.tar.gz\n{HASH_B}  {RG}\n"
    assert expected_sha256(text, RG) == HASH_B


def test_binary_marker_star_is_ignored():
    assert expected_sha256(f"{HASH_B} *{RG}\n", RG) == HASH_B


def test_sidecar_single_line_with_name_matches():
    assert expected_sha256(f"{HASH_B}  {RG}\n", RG) == HASH_B


def test_bare_hash_sidecar_matches_any_asset():
    assert expected_sha256(f"{HASH_B}\n", RG) == HASH_B


def test_path_prefixed_name_matches_by_basename():
    assert expected_sha256(f"{HASH_B}  ./dist/{RG}\n", RG) == HASH_B


def test_uppercase_hex_is_normalized_to_lower():
    assert expected_sha256(f"{'B' * 64}  {RG}\n", RG) == HASH_B


def test_crlf_lines_are_handled():
    text = f"{HASH_A}  other.tar.gz\r\n{HASH_B}  {RG}\r\n"
    assert expected_sha256(text, RG) == HASH_B


def test_asset_not_listed_returns_none():
    assert expected_sha256(f"{HASH_A}  other.tar.gz\n", RG) is None


def test_multiple_bare_hashes_are_not_a_sidecar():
    assert expected_sha256(f"{HASH_A}\n{HASH_B}\n", RG) is None


def test_non_hex_token_is_rejected():
    assert expected_sha256(f"{'z' * 64}  {RG}\n", RG) is None


def test_wrong_length_token_is_rejected():
    assert expected_sha256(f"{'a' * 63}  {RG}\n", RG) is None


def test_empty_text_returns_none():
    assert expected_sha256("", RG) is None


def test_sha256_file_hashes_bytes(tmp_path: Path):
    payload = b"tools-installer"
    target = tmp_path / "asset.tar.gz"
    target.write_bytes(payload)
    assert sha256_file(target) == hashlib.sha256(payload).hexdigest()


def test_checksum_mismatch_message_shows_asset_and_short_digests():
    exc = ChecksumMismatch("a.tar.gz", "12345678" + "a" * 56, "fedcba98" + "b" * 56)
    assert exc.asset == "a.tar.gz"
    assert "a.tar.gz" in str(exc)
    assert "12345678" in str(exc)
    assert "fedcba98" in str(exc)
    assert exc.expected.startswith("12345678")
    assert exc.actual.startswith("fedcba98")
