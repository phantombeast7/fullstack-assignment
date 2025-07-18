from django.urls import path

from chat import views
from .views import (
    ConversationSummaryListView,
    FileUploadView,
    FileListView,
    FileDeleteView,
    RAGQueryView,
    FileProcessView,
)

urlpatterns = [
    path("", views.chat_root_view, name="chat_root_view"),
    path("conversations/", views.get_conversations, name="get_conversations"),
    path("conversations_branched/", views.get_conversations_branched, name="get_branched_conversations"),
    path("conversation_branched/<uuid:pk>/", views.get_conversation_branched, name="get_branched_conversation"),
    path("conversations/add/", views.add_conversation, name="add_conversation"),
    path("conversations/<uuid:pk>/", views.conversation_manage, name="conversation_manage"),
    path("conversations/<uuid:pk>/change_title/", views.conversation_change_title, name="conversation_change_title"),
    path("conversations/<uuid:pk>/add_message/", views.conversation_add_message, name="conversation_add_message"),
    path("conversations/<uuid:pk>/add_version/", views.conversation_add_version, name="conversation_add_version"),
    path(
        "conversations/<uuid:pk>/switch_version/<uuid:version_id>/",
        views.conversation_switch_version,
        name="conversation_switch_version",
    ),
    path("conversations/<uuid:pk>/delete/", views.conversation_soft_delete, name="conversation_delete"),
    path("versions/<uuid:pk>/add_message/", views.version_add_message, name="version_add_message"),
]

urlpatterns += [
    # API endpoints for Task 3
    path('api/conversations/summaries/', ConversationSummaryListView.as_view(), name='conversation-summaries'),
    path('api/files/upload/', FileUploadView.as_view(), name='file-upload'),
    path('api/files/', FileListView.as_view(), name='file-list'),
    path('api/files/<int:id>/delete/', FileDeleteView.as_view(), name='file-delete'),
    # Task 4 endpoints
    path('api/rag/query/', RAGQueryView.as_view(), name='rag-query'),
    path('api/files/<int:id>/process/', FileProcessView.as_view(), name='file-process'),
]
