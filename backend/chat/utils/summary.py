"""
Utility functions for generating conversation summaries.
"""

from typing import List, Dict, Any
from chat.models import Conversation, Message


def generate_conversation_summary(conversation: Conversation) -> str:
    """
    Generate a summary for a conversation based on its messages.
    
    Args:
        conversation: The Conversation object to summarize
        
    Returns:
        str: A generated summary of the conversation
    """
    # Get all messages from the active version
    if not conversation.active_version:
        return "No messages in conversation"
    
    messages = conversation.active_version.messages.all().order_by('created_at')
    
    if not messages.exists():
        return "Empty conversation"
    
    # Create a simple summary based on the first few messages
    message_count = messages.count()
    first_message = messages.first()
    last_message = messages.last()
    
    # Generate a basic summary
    summary_parts = []
    
    if message_count == 1:
        summary_parts.append(f"Single message conversation: {first_message.content[:50]}...")
    else:
        summary_parts.append(f"Conversation with {message_count} messages")
        
        # Add context from first message
        if first_message.role.name == "user":
            summary_parts.append(f"Started with: {first_message.content[:100]}...")
        
        # Add context from last message if different from first
        if last_message != first_message:
            summary_parts.append(f"Latest: {last_message.content[:100]}...")
    
    return " ".join(summary_parts)


def update_conversation_summary(conversation: Conversation) -> None:
    """
    Update the summary field of a conversation.
    
    Args:
        conversation: The Conversation object to update
    """
    summary = generate_conversation_summary(conversation)
    conversation.summary = summary
    conversation.save(update_fields=['summary'], updating_summary=True)


def update_all_conversation_summaries() -> None:
    """
    Update summaries for all conversations that don't have one.
    """
    conversations = Conversation.objects.filter(summary__isnull=True)
    for conversation in conversations:
        update_conversation_summary(conversation) 