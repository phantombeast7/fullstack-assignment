"""
Tests for conversation summary functionality.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from chat.models import Conversation, Version, Message, Role
from chat.utils.summary import generate_conversation_summary, update_conversation_summary

User = get_user_model()


class SummaryTestCase(TestCase):
    """Test cases for conversation summary functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(email='test@example.com', password='testpass')
        self.role_user = Role.objects.create(name='user')
        self.role_assistant = Role.objects.create(name='assistant')
        
    def test_empty_conversation_summary(self):
        """Test summary generation for empty conversation."""
        conversation = Conversation.objects.create(
            title="Test Conversation",
            user=self.user
        )
        
        summary = generate_conversation_summary(conversation)
        self.assertEqual(summary, "No messages in conversation")
        
    def test_single_message_summary(self):
        """Test summary generation for conversation with single message."""
        conversation = Conversation.objects.create(
            title="Test Conversation",
            user=self.user
        )
        version = Version.objects.create(conversation=conversation)
        conversation.active_version = version
        conversation.save()
        
        message = Message.objects.create(
            content="Hello, this is a test message",
            role=self.role_user,
            version=version
        )
        
        summary = generate_conversation_summary(conversation)
        self.assertIn("Single message conversation", summary)
        self.assertIn("Hello, this is a test message", summary)
        
    def test_multiple_messages_summary(self):
        """Test summary generation for conversation with multiple messages."""
        conversation = Conversation.objects.create(
            title="Test Conversation",
            user=self.user
        )
        version = Version.objects.create(conversation=conversation)
        conversation.active_version = version
        conversation.save()
        
        Message.objects.create(
            content="Hello, how are you?",
            role=self.role_user,
            version=version
        )
        Message.objects.create(
            content="I'm doing well, thank you!",
            role=self.role_assistant,
            version=version
        )
        
        summary = generate_conversation_summary(conversation)
        self.assertIn("Conversation with 2 messages", summary)
        self.assertIn("Hello, how are you?", summary)
        # The summary only includes the first and last messages, so we check for the last message
        self.assertIn("I'm doing well, thank you!", summary)
        
    def test_automatic_summary_update(self):
        """Test that summary is automatically updated when conversation is saved."""
        conversation = Conversation.objects.create(
            title="Test Conversation",
            user=self.user
        )
        version = Version.objects.create(conversation=conversation)
        conversation.active_version = version
        conversation.save()
        
        # Initially should have a summary for empty conversation
        conversation.refresh_from_db()
        self.assertIsNotNone(conversation.summary)
        self.assertEqual(conversation.summary, "No messages in conversation")
        
        # Add a message
        Message.objects.create(
            content="Test message",
            role=self.role_user,
            version=version
        )
        
        # Save conversation to trigger summary update
        conversation.save()
        
        # Refresh from database
        conversation.refresh_from_db()
        
        # Should now have a summary with the message content
        self.assertIsNotNone(conversation.summary)
        self.assertIn("Test message", conversation.summary) 