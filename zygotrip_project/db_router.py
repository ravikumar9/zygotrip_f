"""
Section 15 — Database Router for Read Replica

Routes read-only queries for search, analytics, and dashboard models
to the 'replica' database (if configured).

All writes go to 'default'.
"""


class ReadReplicaRouter:
    """
    Route read queries for specific apps to the read replica.
    All writes and migrations go to 'default'.
    """

    # Apps whose reads can safely go to the replica
    REPLICA_APPS = {'search', 'core'}

    # Models within those apps to route (empty = route all models in the app)
    REPLICA_MODELS = {
        'propertysearchindex',
        'analyticsevent',
        'dailymetrics',
        'systemmetrics',
        'performancelog',
    }

    def db_for_read(self, model, **hints):
        if self._should_route_to_replica(model):
            return 'replica'
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == 'default'

    def _should_route_to_replica(self, model):
        app = model._meta.app_label
        model_name = model._meta.model_name
        if app in self.REPLICA_APPS:
            if not self.REPLICA_MODELS or model_name in self.REPLICA_MODELS:
                return True
        return False
