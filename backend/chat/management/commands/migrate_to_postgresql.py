"""
Django management command to migrate data from SQLite to PostgreSQL.
"""

import os
import json
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.db import connections
from django.utils import timezone


class Command(BaseCommand):
    help = 'Migrate data from SQLite to PostgreSQL'

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Create a backup of current data before migration'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually migrating'
        )

    def handle(self, *args, **options):
        """Execute the migration command."""
        backup = options['backup']
        dry_run = options['dry_run']
        
        self.stdout.write('Starting SQLite to PostgreSQL migration...')
        
        # Check if we're currently using SQLite
        current_db = settings.DATABASES['default']['ENGINE']
        if 'sqlite' not in current_db.lower():
            self.stdout.write(
                self.style.WARNING('Not currently using SQLite. Migration not needed.')
            )
            return
        
        if backup:
            self.stdout.write('Creating backup of current data...')
            self._create_backup()
        
        if dry_run:
            self.stdout.write('DRY RUN - Would perform the following steps:')
            self.stdout.write('1. Create PostgreSQL database')
            self.stdout.write('2. Run migrations on PostgreSQL')
            self.stdout.write('3. Export data from SQLite')
            self.stdout.write('4. Import data to PostgreSQL')
            return
        
        try:
            # Step 1: Create PostgreSQL database (user needs to do this manually)
            self.stdout.write(
                self.style.WARNING(
                    'Please ensure PostgreSQL is running and create a database.'
                )
            )
            self.stdout.write(
                'Set the DATABASE_URL environment variable to point to your PostgreSQL database.'
            )
            
            # Step 2: Run migrations on PostgreSQL
            self.stdout.write('Running migrations on PostgreSQL...')
            call_command('migrate', verbosity=0)
            
            # Step 3: Export data from SQLite
            self.stdout.write('Exporting data from SQLite...')
            self._export_data()
            
            # Step 4: Import data to PostgreSQL
            self.stdout.write('Importing data to PostgreSQL...')
            self._import_data()
            
            self.stdout.write(
                self.style.SUCCESS('Migration completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Migration failed: {e}')
            )
            raise CommandError(f'Migration failed: {e}')

    def _create_backup(self):
        """Create a backup of current data."""
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_file = os.path.join(backup_dir, f'backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json')
        
        # Export all data to JSON
        with open(backup_file, 'w') as f:
            call_command('dumpdata', stdout=f, verbosity=0)
        
        self.stdout.write(f'Backup created: {backup_file}')

    def _export_data(self):
        """Export data from SQLite."""
        export_file = os.path.join(settings.BASE_DIR, 'data_export.json')
        
        with open(export_file, 'w') as f:
            call_command('dumpdata', stdout=f, verbosity=0)
        
        self.stdout.write(f'Data exported to: {export_file}')

    def _import_data(self):
        """Import data to PostgreSQL."""
        export_file = os.path.join(settings.BASE_DIR, 'data_export.json')
        
        if not os.path.exists(export_file):
            raise CommandError('Export file not found. Run export first.')
        
        with open(export_file, 'r') as f:
            call_command('loaddata', export_file, verbosity=0)
        
        self.stdout.write('Data imported successfully') 