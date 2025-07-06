from django.contrib.auth.decorators import login_required
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import generics, permissions, filters, status, serializers
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .serializers import ConversationSummarySerializer, FileUploadSerializer
from .models import Conversation, FileUpload, FileEventLog
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from chat.models import Conversation, Message, Version
from chat.serializers import ConversationSerializer, MessageSerializer, TitleSerializer, VersionSerializer
from chat.utils.branching import make_branched_conversation


@api_view(["GET"])
def chat_root_view(request):
    return Response({"message": "Chat works!"}, status=status.HTTP_200_OK)


@login_required
@api_view(["GET"])
def get_conversations(request):
    conversations = Conversation.objects.filter(user=request.user, deleted_at__isnull=True).order_by("-modified_at")
    serializer = ConversationSerializer(conversations, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@login_required
@api_view(["GET"])
def get_conversations_branched(request):
    conversations = Conversation.objects.filter(user=request.user, deleted_at__isnull=True).order_by("-modified_at")
    conversations_serializer = ConversationSerializer(conversations, many=True)
    conversations_data = conversations_serializer.data

    for conversation_data in conversations_data:
        make_branched_conversation(conversation_data)

    return Response(conversations_data, status=status.HTTP_200_OK)


@login_required
@api_view(["GET"])
def get_conversation_branched(request, pk):
    try:
        conversation = Conversation.objects.get(user=request.user, pk=pk)
    except Conversation.DoesNotExist:
        return Response({"detail": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND)

    conversation_serializer = ConversationSerializer(conversation)
    conversation_data = conversation_serializer.data
    make_branched_conversation(conversation_data)

    return Response(conversation_data, status=status.HTTP_200_OK)


@login_required
@api_view(["POST"])
def add_conversation(request):
    try:
        conversation_data = {"title": request.data.get("title", "Mock title"), "user": request.user}
        conversation = Conversation.objects.create(**conversation_data)
        version = Version.objects.create(conversation=conversation)

        messages_data = request.data.get("messages", [])
        for idx, message_data in enumerate(messages_data):
            message_serializer = MessageSerializer(data=message_data)
            if message_serializer.is_valid():
                message_serializer.save(version=version)
                if idx == 0:
                    version.save()
            else:
                return Response(message_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        conversation.active_version = version
        conversation.save()

        serializer = ConversationSerializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@login_required
@api_view(["GET", "PUT", "DELETE"])
def conversation_manage(request, pk):
    try:
        conversation = Conversation.objects.get(user=request.user, pk=pk)
    except Conversation.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = ConversationSerializer(conversation)
        return Response(serializer.data)

    elif request.method == "PUT":
        serializer = ConversationSerializer(conversation, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@login_required
@api_view(["PUT"])
def conversation_change_title(request, pk):
    try:
        conversation = Conversation.objects.get(user=request.user, pk=pk)
    except Conversation.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = TitleSerializer(data=request.data)

    if serializer.is_valid():
        conversation.title = serializer.data.get("title")
        conversation.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    return Response({"detail": "Title not provided"}, status=status.HTTP_400_BAD_REQUEST)


@login_required
@api_view(["PUT"])
def conversation_soft_delete(request, pk):
    try:
        conversation = Conversation.objects.get(user=request.user, pk=pk)
    except Conversation.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    conversation.deleted_at = timezone.now()
    conversation.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


@login_required
@api_view(["POST"])
def conversation_add_message(request, pk):
    try:
        conversation = Conversation.objects.get(user=request.user, pk=pk)
        version = conversation.active_version
    except Conversation.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if version is None:
        return Response({"detail": "Active version not set for this conversation."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = MessageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(version=version)
        # return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(
            {
                "message": serializer.data,
                "conversation_id": conversation.id,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@login_required
@api_view(["POST"])
def conversation_add_version(request, pk):
    try:
        conversation = Conversation.objects.get(user=request.user, pk=pk)
        version = conversation.active_version
        root_message_id = request.data.get("root_message_id")
        root_message = Message.objects.get(pk=root_message_id)
    except Conversation.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    except Message.DoesNotExist:
        return Response({"detail": "Root message not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check if root message belongs to the same conversation
    if root_message.version.conversation != conversation:
        return Response({"detail": "Root message not part of the conversation"}, status=status.HTTP_400_BAD_REQUEST)

    new_version = Version.objects.create(
        conversation=conversation, parent_version=root_message.version, root_message=root_message
    )

    # Copy messages before root_message to new_version
    messages_before_root = Message.objects.filter(version=version, created_at__lt=root_message.created_at)
    new_messages = [
        Message(content=message.content, role=message.role, version=new_version) for message in messages_before_root
    ]
    Message.objects.bulk_create(new_messages)

    # Set the new version as the current version
    conversation.active_version = new_version
    conversation.save()

    serializer = VersionSerializer(new_version)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@login_required
@api_view(["PUT"])
def conversation_switch_version(request, pk, version_id):
    try:
        conversation = Conversation.objects.get(pk=pk)
        version = Version.objects.get(pk=version_id, conversation=conversation)
    except Conversation.DoesNotExist:
        return Response({"detail": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND)
    except Version.DoesNotExist:
        return Response({"detail": "Version not found"}, status=status.HTTP_404_NOT_FOUND)

    conversation.active_version = version
    conversation.save()

    return Response(status=status.HTTP_204_NO_CONTENT)


@login_required
@api_view(["POST"])
def version_add_message(request, pk):
    try:
        version = Version.objects.get(pk=pk)
    except Version.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = MessageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(version=version)
        return Response(
            {
                "message": serializer.data,
                "version_id": version.id,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

@method_decorator(cache_page(60), name='dispatch')
class ConversationSummaryListView(generics.ListAPIView):
    """
    API endpoint to retrieve conversation summaries with pagination and filtering.
    Supports filtering by user, title, and modified_at.
    """
    serializer_class = ConversationSummarySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user', 'title']
    search_fields = ['title', 'summary']
    ordering_fields = ['modified_at', 'title']
    ordering = ['-modified_at']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = Conversation.objects.all()
        user = self.request.query_params.get('user')
        if user:
            qs = qs.filter(user__id=user)
        return qs

class FileUploadPermission(BasePermission):
    """Allow only certain roles to upload/manage files."""
    allowed_roles = ["admin", "user", "moderator", "superadmin"]
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, 'role', None) in self.allowed_roles

class FileUploadView(generics.CreateAPIView):
    """
    API endpoint for file upload with duplication check.
    """
    serializer_class = FileUploadSerializer
    permission_classes = [FileUploadPermission]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        uploaded_file = self.request.FILES['file']
        file_hash = self._calculate_hash(uploaded_file)
        # Check for duplicate
        if FileUpload.objects.filter(hash=file_hash, uploader=self.request.user).exists():
            raise serializers.ValidationError('Duplicate file upload detected.')
        instance = serializer.save(
            uploader=self.request.user,
            name=uploaded_file.name,
            size=uploaded_file.size,
            hash=file_hash
        )
        # Log upload event
        FileEventLog.objects.create(event_type="upload", file=instance, user=self.request.user)

    def _calculate_hash(self, file):
        import hashlib
        hasher = hashlib.sha256()
        for chunk in file.chunks():
            hasher.update(chunk)
        file.seek(0)
        return hasher.hexdigest()

class FileListView(generics.ListAPIView):
    """
    API endpoint to list uploaded files with metadata.
    """
    serializer_class = FileUploadSerializer
    permission_classes = [FileUploadPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['uploader', 'name', 'hash']
    search_fields = ['name']
    ordering_fields = ['uploaded_at', 'name', 'size']
    ordering = ['-uploaded_at']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return FileUpload.objects.filter(uploader=self.request.user)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Log access for each file in the result
        for file in self.get_queryset():
            FileEventLog.objects.create(event_type="access", file=file, user=request.user)
        return response

class FileDeleteView(generics.DestroyAPIView):
    """
    API endpoint to delete an uploaded file.
    """
    serializer_class = FileUploadSerializer
    permission_classes = [FileUploadPermission]
    lookup_field = 'id'

    def get_queryset(self):
        return FileUpload.objects.filter(uploader=self.request.user)

    def perform_destroy(self, instance):
        FileEventLog.objects.create(event_type="delete", file=instance, user=self.request.user)
        super().perform_destroy(instance)

class RAGQueryView(APIView):
    """
    API endpoint for Retrieval-Augmented Generation (RAG) queries.
    POST: {"query": "..."}
    Returns: {"answer": "..."}
    """
    permission_classes = [FileUploadPermission]
    def post(self, request):
        query = request.data.get('query')
        # Stub: Replace with actual RAG logic
        answer = f"[RAG answer for query: {query}]"
        return Response({"answer": answer})

class FileProcessView(APIView):
    """
    API endpoint to process an uploaded file (e.g., extract text, preview, etc.).
    POST: {}
    Returns: {"result": "..."}
    """
    permission_classes = [FileUploadPermission]
    def post(self, request, id):
        try:
            file = FileUpload.objects.get(id=id, uploader=request.user)
        except FileUpload.DoesNotExist:
            return Response({"error": "File not found"}, status=404)
        # Stub: Replace with actual file processing logic
        result = f"[Processed file: {file.name}]"
        return Response({"result": result})
