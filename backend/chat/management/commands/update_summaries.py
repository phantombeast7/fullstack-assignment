"""
Django management command to update conversation summaries.
"""

from django.core.management.base import BaseCommand
from chat.utils.summary import update_all_conversation_summaries


class Command(BaseCommand):
    help = 'Update summaries for all conversations that do not have one'

    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write('Starting to update conversation summaries...')
        
        try:
            update_all_conversation_summaries()
            self.stdout.write(
                self.style.SUCCESS('Successfully updated conversation summaries')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating summaries: {e}')
            ) 