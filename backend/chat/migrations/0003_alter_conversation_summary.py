# Generated by Django 5.0.2 on 2025-07-06 13:04

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0002_conversation_summary"),
    ]

    operations = [
        migrations.AlterField(
            model_name="conversation",
            name="summary",
            field=models.TextField(
                blank=True, help_text="Automatically generated summary of the conversation", null=True
            ),
        ),
    ]
