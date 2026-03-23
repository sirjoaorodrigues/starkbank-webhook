from django.apps import AppConfig


class InvoicesConfig(AppConfig):
    name = 'invoices'

    def ready(self):
        self._setup_periodic_task()

    def _setup_periodic_task(self):
        """Create periodic task for invoice issuance if it doesn't exist."""
        try:
            from django_celery_beat.models import PeriodicTask, IntervalSchedule
            from django.db import connection

            if 'django_celery_beat_periodictask' not in connection.introspection.table_names():
                return

            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=3,
                period=IntervalSchedule.HOURS
            )

            PeriodicTask.objects.get_or_create(
                name='Issue invoices every 3 hours',
                defaults={
                    'task': 'invoices.tasks.issue_invoices',
                    'interval': schedule,
                    'enabled': True
                }
            )
        except Exception:
            pass
