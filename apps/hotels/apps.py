from django.apps import AppConfig


class HotelsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.hotels"
    label = "hotels"

    def ready(self):
        """
        Wire up search-index rebuild on post-migrate.
        Runs once per server start (after all migrations are applied).
        Guards against running during makemigrations / test collection.
        """
        from django.db.models.signals import post_migrate

        def _rebuild_search_index(sender, **kwargs):
            """Rebuild the SearchIndex table from live City/Locality/Property data."""
            import sys
            # Skip during management commands that don't need the index
            skip_cmds = {'makemigrations', 'migrate', 'collectstatic', 'test', 'shell'}
            if len(sys.argv) > 1 and sys.argv[1] in skip_cmds:
                return
            try:
                from apps.search.index_builder import rebuild_search_index
                rebuild_search_index()
            except Exception as exc:  # pragma: no cover
                import logging
                logging.getLogger('zygotrip.hotels').warning(
                    "Search index rebuild skipped at startup: %s", exc
                )

        post_migrate.connect(_rebuild_search_index, sender=self)