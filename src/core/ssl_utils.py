import datetime
import logging
from pathlib import Path

logger = logging.getLogger("QQBot")


def generate_self_signed_cert(cert_path: Path, key_path: Path, hostname: str = "localhost"):
    import ipaddress

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        logger.error("生成自签名证书需要 cryptography 库，请执行: pip install cryptography")
        return False

    try:
        ipaddress.ip_address(hostname)
        san = [x509.IPAddress(ipaddress.IPv4Address(hostname))]
        is_ip = True
    except ValueError:
        san = [x509.DNSName(hostname)]
        is_ip = False

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Guangdong"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Shenzhen"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "QQBot"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(san),
            critical=False,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    mode = "IP" if is_ip else "域名"
    logger.info(f"🔐 已生成自签名证书 (CN={hostname}, {mode}): {cert_path}")
    return True
