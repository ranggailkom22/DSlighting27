from django.core.management.base import BaseCommand
from core.utils import cancel_expired_pending_orders


class Command(BaseCommand):
    help = 'Cancel pending orders that have not been paid within 2 hours'

    def handle(self, *args, **options):
        cancelled_count = cancel_expired_pending_orders()
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cancelled {cancelled_count} expired pending orders'
            )
        )