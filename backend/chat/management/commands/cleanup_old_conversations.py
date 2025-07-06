"""
Django management command to clean up old conversations.
"""

import os
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from chat.models import Conversation, Message, Version
from django.db import models


class Command(BaseCommand):
    help = 'Clean up old conversations based on age and deletion status'

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days after which conversations are considered old (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without confirmation'
        )
        parser.add_argument(
            '--deleted-only',
            action='store_true',
            help='Only clean up conversations that are already soft-deleted'
        )

    def handle(self, *args, **options):
        """Execute the cleanup command."""
        days = options['days']
        dry_run = options['dry_run']
        force = options['force']
        deleted_only = options['deleted_only']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(f'Starting cleanup of conversations older than {days} days...')
        self.stdout.write(f'Cutoff date: {cutoff_date}')
        
        # Build the query
        if deleted_only:
            query = Conversation.objects.filter(deleted_at__isnull=False, modified_at__lt=cutoff_date)
            self.stdout.write('Only cleaning up soft-deleted conversations')
        else:
            query = Conversation.objects.filter(modified_at__lt=cutoff_date)
            self.stdout.write('Cleaning up all conversations older than cutoff (regardless of deletion status)')
        
        conversations_to_delete = query.count()
        
        if conversations_to_delete == 0:
            self.stdout.write(
                self.style.SUCCESS('No conversations found to clean up')
            )
            return
        
        self.stdout.write(f'Found {conversations_to_delete} conversations to clean up')
        
        if dry_run:
            self.stdout.write('DRY RUN - No changes will be made')
            for conversation in query[:5]:  # Show first 5 as examples
                self.stdout.write(f'  - {conversation.title} (modified: {conversation.modified_at})')
            if conversations_to_delete > 5:
                self.stdout.write(f'  ... and {conversations_to_delete - 5} more')
            return
        
        if not force:
            confirm = input(f'\nAre you sure you want to delete {conversations_to_delete} conversations? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write('Cleanup cancelled')
                return
        
        # Perform the cleanup
        try:
            with transaction.atomic():
                deleted_count = 0
                for conversation in query.iterator():
                    # Delete related objects first
                    Message.objects.filter(version__conversation=conversation).delete()
                    Version.objects.filter(conversation=conversation).delete()
                    conversation.delete()
                    deleted_count += 1
                    
                    if deleted_count % 100 == 0:
                        self.stdout.write(f'Processed {deleted_count} conversations...')
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully cleaned up {deleted_count} conversations'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during cleanup: {e}')
            )
            raise CommandError(f'Cleanup failed: {e}') 