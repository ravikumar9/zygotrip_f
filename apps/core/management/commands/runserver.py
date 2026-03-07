import os
from pathlib import Path

import trustme
import uvicorn
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.management.base import BaseCommand
from django.core.management.commands.runserver import Command as DjangoRunserverCommand
from django.core.asgi import get_asgi_application


def _ensure_cert_files(cert_dir: Path) -> tuple[Path, Path]:
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "dev_cert.pem"
    key_path = cert_dir / "dev_key.pem"

    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    ca = trustme.CA()
    server_cert = ca.issue_cert("127.0.0.1", "localhost")
    server_cert.cert_chain_pems[0].write_to_path(cert_path)
    server_cert.private_key_pem.write_to_path(key_path)

    return cert_path, key_path


def _parse_addrport(addrport: str | None) -> tuple[str, int]:
    if not addrport:
        return "127.0.0.1", 8000

    if ":" in addrport:
        host, port_str = addrport.rsplit(":", 1)
        host = host or "127.0.0.1"
        return host, int(port_str)

    return "127.0.0.1", int(addrport)


class Command(BaseCommand):
    help = "Run the development server over HTTPS by default."

    def add_arguments(self, parser):
        parser.add_argument("addrport", nargs="?", help="Optional host:port or port")
        parser.add_argument(
            "--http",
            action="store_true",
            help="Use Django's default HTTP development server",
        )
        parser.add_argument(
            "--noreload",
            action="store_true",
            help="Disable auto-reload",
        )

    def handle(self, *args, **options):
        if options.get("http"):
            django_cmd = DjangoRunserverCommand()
            return django_cmd.execute(*args, **options)

        host, port = _parse_addrport(options.get("addrport"))
        base_dir = Path(__file__).resolve().parents[4]
        cert_dir = base_dir / ".devcert"
        cert_path, key_path = _ensure_cert_files(cert_dir)

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zygotrip_project.settings")
        application = ASGIStaticFilesHandler(get_asgi_application())

        reload_enabled = settings.DEBUG and not options.get("noreload")

        uvicorn.run(
            application,
            host=host,
            port=port,
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
            log_level="info",
            reload=reload_enabled,
        )
