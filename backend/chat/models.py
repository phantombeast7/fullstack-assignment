import uuid

from django.db import models
from django.conf import settings
import hashlib

from authentication.models import CustomUser


class Role(models.Model):
    name = models.CharField(max_length=20, blank=False, null=False, default="user")

    def __str__(self):
        return self.name


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100, blank=False, null=False, default="Mock title")
    summary = models.TextField(blank=True, null=True, help_text="Automatically generated summary of the conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    active_version = models.ForeignKey(
        "Version", null=True, blank=True, on_delete=models.CASCADE, related_name="current_version_conversations"
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

    def version_count(self):
        return self.versions.count()

    version_count.short_description = "Number of versions"
    
    def save(self, *args, **kwargs):
        """Override save to automatically update summary when conversation is modified."""
        # Check if we're already updating the summary to prevent recursion
        updating_summary = kwargs.pop('updating_summary', False)
        
        super().save(*args, **kwargs)
        
        # Update summary if this is a new conversation or if active_version changed
        if not updating_summary and (not self.summary or (self.active_version and self.active_version.messages.exists())):
            from chat.utils.summary import update_conversation_summary
            update_conversation_summary(self)


class Version(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey("Conversation", related_name="versions", on_delete=models.CASCADE)
    parent_version = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    root_message = models.ForeignKey(
        "Message", null=True, blank=True, on_delete=models.SET_NULL, related_name="root_message_versions"
    )

    def __str__(self):
        if self.root_message:
            return f"Version of `{self.conversation.title}` created at `{self.root_message.created_at}`"
        else:
            return f"Version of `{self.conversation.title}` with no root message yet"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField(blank=False, null=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.ForeignKey("Version", related_name="messages", on_delete=models.CASCADE)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        self.version.conversation.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.role}: {self.content[:20]}..."


class FileUpload(models.Model):
    file = models.FileField(upload_to='uploads/')
    name = models.CharField(max_length=255)
    size = models.BigIntegerField()
    hash = models.CharField(max_length=64, db_index=True)
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('hash', 'uploader')
        ordering = ['-uploaded_at']

    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = self.calculate_hash()
        if not self.size:
            self.size = self.file.size
        super().save(*args, **kwargs)

    def calculate_hash(self):
        """Calculate SHA256 hash of the file contents."""
        import hashlib
        hasher = hashlib.sha256()
        self.file.seek(0)
        # Support both .chunks() and .read() for test compatibility
        if hasattr(self.file, 'chunks'):
            for chunk in self.file.chunks():
                hasher.update(chunk)
        else:
            hasher.update(self.file.read())
        self.file.seek(0)
        return hasher.hexdigest()

    def __str__(self):
        return f"{self.name} ({self.size} bytes)"


class FileEventLog(models.Model):
    EVENT_CHOICES = [
        ("upload", "Upload"),
        ("delete", "Delete"),
        ("access", "Access"),
    ]
    event_type = models.CharField(max_length=10, choices=EVENT_CHOICES)
    file = models.ForeignKey(FileUpload, on_delete=models.SET_NULL, null=True, related_name='logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    extra = models.TextField(blank=True, null=True, help_text="Optional extra info (e.g., IP, user agent)")

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.event_type} by {self.user} on {self.file} at {self.timestamp}"
