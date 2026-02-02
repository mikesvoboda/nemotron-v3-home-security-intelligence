"""Unit tests for setup_lib.ssl_certs module.

Tests SSL certificate generation, validation, and interactive prompts for HTTPS setup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGetLocalIp:
    """Tests for get_local_ip() function."""

    def test_returns_local_ip_address(self) -> None:
        """Should return the detected local IP address."""
        from setup_lib.ssl_certs import get_local_ip

        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ("192.168.1.100", 0)

        with patch("socket.socket") as mock_socket_class:
            mock_socket_class.return_value.__enter__.return_value = mock_socket
            result = get_local_ip()

            assert result == "192.168.1.100"
            mock_socket.connect.assert_called_once_with(("8.8.8.8", 80))

    def test_returns_none_on_socket_error(self) -> None:
        """Should return None when socket connection fails."""
        from setup_lib.ssl_certs import get_local_ip

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket.connect.side_effect = OSError("Network unreachable")
            mock_socket_class.return_value.__enter__.return_value = mock_socket

            result = get_local_ip()
            assert result is None

    def test_returns_different_ip_addresses(self) -> None:
        """Should return different IP addresses based on network configuration."""
        from setup_lib.ssl_certs import get_local_ip

        test_ips = ["10.0.0.50", "172.16.0.25", "192.168.0.1"]

        for expected_ip in test_ips:
            mock_socket = MagicMock()
            mock_socket.getsockname.return_value = (expected_ip, 0)

            with patch("socket.socket") as mock_socket_class:
                mock_socket_class.return_value.__enter__.return_value = mock_socket
                result = get_local_ip()
                assert result == expected_ip


class TestGenerateSelfSignedCert:
    """Tests for generate_self_signed_cert() function."""

    def test_returns_false_without_cryptography(self, tmp_path: Path) -> None:
        """Should return False when cryptography library is not available."""
        from setup_lib import ssl_certs

        original_value = ssl_certs.CRYPTOGRAPHY_AVAILABLE

        try:
            ssl_certs.CRYPTOGRAPHY_AVAILABLE = False

            with patch("builtins.print") as mock_print:
                result = ssl_certs.generate_self_signed_cert(
                    cert_path=tmp_path / "cert.pem",
                    key_path=tmp_path / "key.pem",
                )

                assert result is False
                mock_print.assert_any_call("! cryptography library not installed")
        finally:
            ssl_certs.CRYPTOGRAPHY_AVAILABLE = original_value

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Should create parent directories for cert and key paths."""
        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_dir = tmp_path / "certs" / "nested"
        cert_path = cert_dir / "cert.pem"
        key_path = cert_dir / "key.pem"

        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
        )

        assert result is True
        assert cert_dir.exists()
        assert cert_path.exists()
        assert key_path.exists()

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_generates_valid_certificate(self, tmp_path: Path) -> None:
        """Should generate a valid self-signed certificate."""
        from cryptography import x509
        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            hostname="test.local",
        )

        assert result is True

        # Verify certificate can be loaded
        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        # Check common name
        cn = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0]
        assert cn.value == "test.local"

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_includes_default_sans(self, tmp_path: Path) -> None:
        """Should include default SANs (localhost, 127.0.0.1, ::1)."""
        from cryptography import x509
        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
        )

        assert result is True

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        # Get SAN extension
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        san_names = san_ext.value

        # Check for default DNS names
        dns_names = [name.value for name in san_names if isinstance(name, x509.DNSName)]
        assert "localhost" in dns_names
        assert "*.localhost" in dns_names

        # Check for default IP addresses
        ip_addresses = [str(name.value) for name in san_names if isinstance(name, x509.IPAddress)]
        assert "127.0.0.1" in ip_addresses
        assert "::1" in ip_addresses

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_includes_custom_san_ips(self, tmp_path: Path) -> None:
        """Should include custom SAN IP addresses."""
        from cryptography import x509
        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            san_ips=["192.168.1.100", "10.0.0.1"],
        )

        assert result is True

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        ip_addresses = [
            str(name.value) for name in san_ext.value if isinstance(name, x509.IPAddress)
        ]

        assert "192.168.1.100" in ip_addresses
        assert "10.0.0.1" in ip_addresses

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_includes_custom_san_dns(self, tmp_path: Path) -> None:
        """Should include custom SAN DNS names."""
        from cryptography import x509
        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            san_dns=["myserver.local", "dashboard.home"],
        )

        assert result is True

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = [name.value for name in san_ext.value if isinstance(name, x509.DNSName)]

        assert "myserver.local" in dns_names
        assert "dashboard.home" in dns_names

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_respects_days_valid_parameter(self, tmp_path: Path) -> None:
        """Should set certificate validity period correctly."""
        from cryptography import x509
        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            days_valid=730,  # 2 years
        )

        assert result is True

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        # Check validity period (approximately 2 years)
        now = datetime.now(UTC)
        validity_days = (cert.not_valid_after_utc - now).days
        assert 728 <= validity_days <= 731  # Allow small margin

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_sets_key_file_permissions(self, tmp_path: Path) -> None:
        """Should set private key file permissions to 600."""
        import stat

        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
        )

        assert result is True

        # Check permissions (owner read/write only)
        key_mode = key_path.stat().st_mode & 0o777
        assert key_mode == (stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_skips_invalid_ip_addresses(self, tmp_path: Path) -> None:
        """Should skip invalid IP addresses without crashing."""
        from cryptography import x509
        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        # Include both valid and invalid IPs
        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            san_ips=["192.168.1.100", "not-an-ip", "10.0.0.1"],
        )

        assert result is True

        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        ip_addresses = [
            str(name.value) for name in san_ext.value if isinstance(name, x509.IPAddress)
        ]

        # Valid IPs should be included
        assert "192.168.1.100" in ip_addresses
        assert "10.0.0.1" in ip_addresses
        # Invalid IP should be skipped (no crash)

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_generates_rsa_key_with_correct_size(self, tmp_path: Path) -> None:
        """Should generate RSA key with specified key size."""
        from cryptography.hazmat.primitives import serialization
        from setup_lib.ssl_certs import generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        result = generate_self_signed_cert(
            cert_path=cert_path,
            key_path=key_path,
            key_size=4096,
        )

        assert result is True

        key_data = key_path.read_bytes()
        private_key = serialization.load_pem_private_key(key_data, password=None)
        assert private_key.key_size == 4096


class TestCheckExistingCertificates:
    """Tests for check_existing_certificates() function."""

    def test_returns_false_when_cert_missing(self, tmp_path: Path) -> None:
        """Should return False when certificate file doesn't exist."""
        from setup_lib.ssl_certs import check_existing_certificates

        cert_path = tmp_path / "nonexistent_cert.pem"
        key_path = tmp_path / "key.pem"
        key_path.write_text("dummy key")

        result = check_existing_certificates(cert_path, key_path)
        assert result is False

    def test_returns_false_when_key_missing(self, tmp_path: Path) -> None:
        """Should return False when key file doesn't exist."""
        from setup_lib.ssl_certs import check_existing_certificates

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "nonexistent_key.pem"
        cert_path.write_text("dummy cert")

        result = check_existing_certificates(cert_path, key_path)
        assert result is False

    def test_returns_false_when_both_missing(self, tmp_path: Path) -> None:
        """Should return False when both files are missing."""
        from setup_lib.ssl_certs import check_existing_certificates

        cert_path = tmp_path / "nonexistent_cert.pem"
        key_path = tmp_path / "nonexistent_key.pem"

        result = check_existing_certificates(cert_path, key_path)
        assert result is False

    def test_returns_true_when_cryptography_unavailable_and_files_exist(
        self, tmp_path: Path
    ) -> None:
        """Should return True when files exist but cryptography is unavailable."""
        from setup_lib import ssl_certs

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"
        cert_path.write_text("dummy cert")
        key_path.write_text("dummy key")

        original_value = ssl_certs.CRYPTOGRAPHY_AVAILABLE

        try:
            ssl_certs.CRYPTOGRAPHY_AVAILABLE = False
            result = ssl_certs.check_existing_certificates(cert_path, key_path)
            assert result is True
        finally:
            ssl_certs.CRYPTOGRAPHY_AVAILABLE = original_value

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_returns_true_for_valid_certificate(self, tmp_path: Path) -> None:
        """Should return True for a valid, non-expired certificate."""
        from setup_lib.ssl_certs import check_existing_certificates, generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        # Generate a valid certificate
        generate_self_signed_cert(cert_path, key_path, days_valid=365)

        result = check_existing_certificates(cert_path, key_path)
        assert result is True

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_returns_false_for_nearly_expired_certificate(self, tmp_path: Path) -> None:
        """Should return False when certificate has less than 7 days remaining."""
        from setup_lib.ssl_certs import check_existing_certificates, generate_self_signed_cert

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        # Generate a certificate valid for only 5 days
        generate_self_signed_cert(cert_path, key_path, days_valid=5)

        result = check_existing_certificates(cert_path, key_path)
        assert result is False

    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not installed"),
        reason="cryptography library not installed",
    )
    def test_returns_false_for_corrupted_certificate(self, tmp_path: Path) -> None:
        """Should return False when certificate file is corrupted."""
        from setup_lib.ssl_certs import check_existing_certificates

        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"
        cert_path.write_text("not a valid certificate")
        key_path.write_text("not a valid key")

        result = check_existing_certificates(cert_path, key_path)
        assert result is False


class TestPromptAndGenerateCertificates:
    """Tests for prompt_and_generate_certificates() function."""

    def test_prints_header_information(self) -> None:
        """Should print SSL/TLS header information."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("builtins.input", return_value="n"),
            patch("builtins.print") as mock_print,
        ):
            prompt_and_generate_certificates({})

            # Verify header is printed
            calls = [str(c) for c in mock_print.call_args_list]
            header_found = any("SSL/TLS Certificate Generation" in str(c) for c in calls)
            assert header_found

    def test_skips_generation_when_user_declines(self) -> None:
        """Should skip certificate generation when user says no."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("builtins.input", return_value="n"),
            patch("builtins.print") as mock_print,
            patch("setup_lib.ssl_certs.generate_self_signed_cert") as mock_generate,
        ):
            prompt_and_generate_certificates({})

            mock_generate.assert_not_called()
            # Should print skip message
            calls = [str(c) for c in mock_print.call_args_list]
            skip_found = any("Skipping certificate generation" in str(c) for c in calls)
            assert skip_found

    def test_prompts_to_regenerate_when_certs_exist(self) -> None:
        """Should ask about regenerating when valid certificates exist."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=True),
            patch("builtins.input", return_value="n"),
            patch("builtins.print") as mock_print,
            patch("setup_lib.ssl_certs.generate_self_signed_cert") as mock_generate,
        ):
            prompt_and_generate_certificates({})

            # Should ask about regeneration
            mock_generate.assert_not_called()
            calls = [str(c) for c in mock_print.call_args_list]
            exists_found = any("Existing valid certificates found" in str(c) for c in calls)
            assert exists_found

    def test_keeps_existing_certs_when_user_declines_regeneration(self) -> None:
        """Should keep existing certificates when user declines regeneration."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=True),
            patch("builtins.input", return_value="n"),
            patch("builtins.print") as mock_print,
            patch("setup_lib.ssl_certs.generate_self_signed_cert") as mock_generate,
        ):
            prompt_and_generate_certificates({})

            mock_generate.assert_not_called()
            calls = [str(c) for c in mock_print.call_args_list]
            keep_found = any("Keeping existing certificates" in str(c) for c in calls)
            assert keep_found

    def test_detects_local_ip_and_prompts_for_san(self) -> None:
        """Should detect local IP and prompt to add it to SANs."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, default hostname, yes to add IP, no extra IPs
        input_responses = iter(["y", "", "y", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value="192.168.1.100"),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print") as mock_print,
            patch("setup_lib.ssl_certs.generate_self_signed_cert", return_value=True),
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            # Should print detected IP
            calls = [str(c) for c in mock_print.call_args_list]
            ip_found = any("192.168.1.100" in str(c) for c in calls)
            assert ip_found

    def test_adds_detected_ip_to_sans_when_confirmed(self) -> None:
        """Should add detected local IP to SANs when user confirms."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, default hostname, yes to add IP, no extra IPs
        input_responses = iter(["y", "", "y", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value="192.168.1.100"),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print"),
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert", return_value=True
            ) as mock_generate,
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            # Verify generate was called with the IP in san_ips
            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args.kwargs
            assert "192.168.1.100" in call_kwargs.get("san_ips", [])

    def test_skips_local_ip_when_user_declines(self) -> None:
        """Should not add local IP to SANs when user declines."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, default hostname, no to add IP, no extra IPs
        input_responses = iter(["y", "", "n", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value="192.168.1.100"),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print"),
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert", return_value=True
            ) as mock_generate,
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            # Verify generate was called without the IP in san_ips
            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args.kwargs
            assert "192.168.1.100" not in call_kwargs.get("san_ips", [])

    def test_accepts_additional_ip_addresses(self) -> None:
        """Should accept additional IP addresses from user input."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, default hostname, no to add detected IP, extra IPs
        input_responses = iter(["y", "", "n", "10.0.0.1, 172.16.0.5"])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value="192.168.1.100"),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print"),
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert", return_value=True
            ) as mock_generate,
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args.kwargs
            san_ips = call_kwargs.get("san_ips", [])
            assert "10.0.0.1" in san_ips
            assert "172.16.0.5" in san_ips

    def test_validates_additional_ip_addresses(self) -> None:
        """Should validate and skip invalid additional IP addresses."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs with invalid IP
        # When get_local_ip returns None, no prompt for adding detected IP
        # Flow: generate?, hostname, extra IPs
        input_responses = iter(["y", "", "10.0.0.1, invalid-ip, 172.16.0.5"])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print") as mock_print,
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert", return_value=True
            ) as mock_generate,
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            # Should print warning about invalid IP
            calls = [str(c) for c in mock_print.call_args_list]
            invalid_found = any("Invalid IP address" in str(c) for c in calls)
            assert invalid_found

            # Valid IPs should still be included
            call_kwargs = mock_generate.call_args.kwargs
            san_ips = call_kwargs.get("san_ips", [])
            assert "10.0.0.1" in san_ips
            assert "172.16.0.5" in san_ips

    def test_uses_custom_hostname_when_provided(self) -> None:
        """Should use custom hostname when user provides one."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, custom hostname, no extra IPs
        input_responses = iter(["y", "myserver.local", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="defaulthost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print"),
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert", return_value=True
            ) as mock_generate,
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs.get("hostname") == "myserver.local"

    def test_uses_default_hostname_when_empty(self) -> None:
        """Should use detected hostname when user provides empty input."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, empty (use default) hostname, no extra IPs
        input_responses = iter(["y", "", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="detected-hostname"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print"),
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert", return_value=True
            ) as mock_generate,
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs.get("hostname") == "detected-hostname"

    def test_shows_error_when_cryptography_unavailable(self) -> None:
        """Should show error message when cryptography is unavailable."""
        from setup_lib import ssl_certs

        # Mock inputs: yes to generate, default hostname, no extra IPs
        input_responses = iter(["y", "", ""])

        original_value = ssl_certs.CRYPTOGRAPHY_AVAILABLE

        try:
            ssl_certs.CRYPTOGRAPHY_AVAILABLE = False

            with (
                patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
                patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
                patch("socket.gethostname", return_value="testhost"),
                patch("builtins.input", side_effect=lambda _: next(input_responses)),
                patch("builtins.print") as mock_print,
            ):
                ssl_certs.prompt_and_generate_certificates({})

                calls = [str(c) for c in mock_print.call_args_list]
                error_found = any("cryptography library not installed" in str(c) for c in calls)
                assert error_found
        finally:
            ssl_certs.CRYPTOGRAPHY_AVAILABLE = original_value

    def test_prints_success_message_after_generation(self) -> None:
        """Should print success message after certificate generation."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, default hostname, no extra IPs
        input_responses = iter(["y", "", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print") as mock_print,
            patch("setup_lib.ssl_certs.generate_self_signed_cert", return_value=True),
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            calls = [str(c) for c in mock_print.call_args_list]
            cert_generated = any("Certificate generated" in str(c) for c in calls)
            key_generated = any("Private key generated" in str(c) for c in calls)
            assert cert_generated
            assert key_generated

    def test_prints_failure_message_on_error(self) -> None:
        """Should print failure message when generation fails."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, default hostname, no extra IPs
        input_responses = iter(["y", "", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print") as mock_print,
            patch("setup_lib.ssl_certs.generate_self_signed_cert", return_value=False),
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            calls = [str(c) for c in mock_print.call_args_list]
            failure_found = any("Failed to generate certificate" in str(c) for c in calls)
            assert failure_found

    def test_handles_generation_exception(self) -> None:
        """Should handle exceptions during certificate generation."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, default hostname, no extra IPs
        input_responses = iter(["y", "", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print") as mock_print,
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert",
                side_effect=Exception("Permission denied"),
            ),
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            # Should not raise exception
            prompt_and_generate_certificates({})

            calls = [str(c) for c in mock_print.call_args_list]
            error_found = any("Error generating certificate" in str(c) for c in calls)
            assert error_found

    def test_shows_browser_warning_after_success(self) -> None:
        """Should show browser security warning after successful generation."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes to generate, default hostname, no extra IPs
        input_responses = iter(["y", "", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print") as mock_print,
            patch("setup_lib.ssl_certs.generate_self_signed_cert", return_value=True),
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})

            calls = [str(c) for c in mock_print.call_args_list]
            warning_found = any("security warning" in str(c).lower() for c in calls)
            assert warning_found

    @pytest.mark.parametrize("yes_input", ["y", "Y", "yes", "YES", "Yes"])
    def test_accepts_yes_variations(self, yes_input: str) -> None:
        """Should accept various forms of 'yes' input."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: yes variation to generate, default hostname, no extra IPs
        input_responses = iter([yes_input, "", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print"),
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert", return_value=True
            ) as mock_generate,
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})
            mock_generate.assert_called_once()

    def test_default_generation_on_empty_input(self) -> None:
        """Should default to generating certificate on empty input."""
        from setup_lib.ssl_certs import prompt_and_generate_certificates

        # Mock inputs: empty (default yes), default hostname, no extra IPs
        input_responses = iter(["", "", ""])

        with (
            patch("setup_lib.ssl_certs.check_existing_certificates", return_value=False),
            patch("setup_lib.ssl_certs.get_local_ip", return_value=None),
            patch("socket.gethostname", return_value="testhost"),
            patch("builtins.input", side_effect=lambda _: next(input_responses)),
            patch("builtins.print"),
            patch(
                "setup_lib.ssl_certs.generate_self_signed_cert", return_value=True
            ) as mock_generate,
            patch("setup_lib.ssl_certs.CRYPTOGRAPHY_AVAILABLE", True),
        ):
            prompt_and_generate_certificates({})
            mock_generate.assert_called_once()


class TestCryptographyAvailability:
    """Tests for CRYPTOGRAPHY_AVAILABLE constant."""

    def test_cryptography_available_is_boolean(self) -> None:
        """Should be a boolean value."""
        from setup_lib.ssl_certs import CRYPTOGRAPHY_AVAILABLE

        assert isinstance(CRYPTOGRAPHY_AVAILABLE, bool)

    def test_cryptography_available_when_installed(self) -> None:
        """Should be True when cryptography is installed."""
        try:
            import cryptography  # noqa: F401
            from setup_lib.ssl_certs import CRYPTOGRAPHY_AVAILABLE

            assert CRYPTOGRAPHY_AVAILABLE is True
        except ImportError:
            pytest.skip("cryptography not installed")
