# Generated by Django 5.0.2 on 2025-07-06 12:59

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="summary",
            field=models.TextField(blank=True, null=True),
        ),
    ]
