from django.core.management.base import BaseCommand
from invoices.models import InvoiceCampaign


class Command(BaseCommand):
    help = 'Start a new invoice campaign (8 executions over 24 hours)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-executions',
            type=int,
            default=8,
            help='Maximum number of executions (default: 8)'
        )
        parser.add_argument(
            '--deactivate-previous',
            action='store_true',
            help='Deactivate any previous active campaigns'
        )

    def handle(self, *args, **options):
        max_executions = options['max_executions']
        deactivate_previous = options['deactivate_previous']

        if deactivate_previous:
            count = InvoiceCampaign.objects.filter(is_active=True).update(is_active=False)
            if count:
                self.stdout.write(f'Deactivated {count} previous campaign(s)')

        active_campaigns = InvoiceCampaign.objects.filter(is_active=True).count()
        if active_campaigns > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'There are {active_campaigns} active campaign(s). '
                    'Use --deactivate-previous to deactivate them first.'
                )
            )
            return

        campaign = InvoiceCampaign.objects.create(max_executions=max_executions)

        self.stdout.write(
            self.style.SUCCESS(
                f'Campaign {campaign.id} started! '
                f'Will run {max_executions} times over {max_executions * 3} hours.'
            )
        )
