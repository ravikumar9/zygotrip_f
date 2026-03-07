import os
import re
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


HEX_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}")
ALLOWED_EXTENSIONS = {
	".css",
	".html",
	".js",
	".ts",
	".py",
}


class Command(BaseCommand):
	help = "Validate that no unauthorized hex colors exist outside tokens.css."

	def handle(self, *args, **options):
		base_dir = settings.BASE_DIR
		allowed = self._load_allowed_hex(base_dir)
		violations = []
		for root, dirs, files in os.walk(base_dir):
			dirs[:] = [
				d
				for d in dirs
				if d not in {".git", ".venv", "node_modules", "staticfiles"}
			]
			for filename in files:
				if filename == "tokens.css":
					continue
				ext = os.path.splitext(filename)[1].lower()
				if ext not in ALLOWED_EXTENSIONS:
					continue
				path = os.path.join(root, filename)
				matches = self._scan_file(path, allowed)
				if matches:
					violations.extend(matches)

		if violations:
			message = "Unauthorized hex colors found:\n" + "\n".join(violations)
			raise CommandError(message)

		self.stdout.write(self.style.SUCCESS("Color validation passed."))

	def _load_allowed_hex(self, base_dir):
		tokens_path = os.path.join(base_dir, "static", "css", "tokens.css")
		try:
			with open(tokens_path, "r", encoding="utf-8") as handle:
				content = handle.read()
		except FileNotFoundError as exc:
			raise CommandError("tokens.css not found") from exc
		return {value.lower() for value in HEX_PATTERN.findall(content)}

	def _scan_file(self, path, allowed):
		try:
			with open(path, "r", encoding="utf-8") as handle:
				content = handle.read()
		except UnicodeDecodeError:
			with open(path, "r", encoding="latin-1", errors="ignore") as handle:
				content = handle.read()

		results = []
		for match in HEX_PATTERN.finditer(content):
			value = match.group(0).lower()
			if value not in allowed:
				rel_path = os.path.relpath(path, settings.BASE_DIR)
				results.append(f"{rel_path}: {match.group(0)}")
		return results
