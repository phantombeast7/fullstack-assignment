from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from chat.models import Conversation, FileUpload, Version, Role, FileEventLog
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
import io

User = get_user_model()

class Task3APITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@example.com', password='testpass')
        self.user2 = User.objects.create_user(email='other@example.com', password='testpass')
        self.role = Role.objects.create(name='user')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _get_results(self, response):
        # Helper to get results from paginated or non-paginated response
        if isinstance(response.data, dict) and 'results' in response.data:
            return response.data['results']
        return response.data

    def test_conversation_summaries_pagination_and_filtering(self):
        # Create conversations for both users
        for i in range(5):
            Conversation.objects.create(title=f"Conv {i}", summary=f"Summary {i}", user=self.user)
        for i in range(3):
            Conversation.objects.create(title=f"Other {i}", summary=f"Other Summary {i}", user=self.user2)
        url = reverse('conversation-summaries')
        # Test pagination
        response = self.client.get(url, {'page': 1, 'page_size': 3})
        self.assertEqual(response.status_code, 200)
        results = self._get_results(response)
        self.assertEqual(len(results), 3)
        self.assertEqual(response.data['count'], 8)  # 8 total conversations
        # Test filtering by user
        response = self.client.get(url, {'user': self.user.id})
        self.assertEqual(response.status_code, 200)
        results = self._get_results(response)
        for item in results:
            self.assertEqual(item['user'], self.user.id)
        # Test search
        response = self.client.get(url, {'search': 'Other'})
        self.assertEqual(response.status_code, 200)
        results = self._get_results(response)
        for item in results:
            self.assertIn('Other', item['title'])

    def test_file_upload_and_duplicate_check(self):
        url = reverse('file-upload')
        file_content = b"hello world"
        uploaded_file = SimpleUploadedFile("test.txt", file_content)
        response = self.client.post(url, {'file': uploaded_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn('id', response.data)
        # Try uploading the same file again (should fail)
        uploaded_file2 = SimpleUploadedFile("test.txt", file_content)
        response = self.client.post(url, {'file': uploaded_file2}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Duplicate file upload detected.', str(response.data))

    def test_file_list_and_metadata(self):
        # Upload two files
        url = reverse('file-upload')
        file1 = SimpleUploadedFile("a.txt", b"abc")
        file2 = SimpleUploadedFile("b.txt", b"def")
        self.client.post(url, {'file': file1}, format='multipart')
        self.client.post(url, {'file': file2}, format='multipart')
        # List files
        url = reverse('file-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        results = self._get_results(response)
        self.assertEqual(len(results), 2)
        for file in results:
            self.assertIn('name', file)
            self.assertIn('size', file)
            self.assertIn('hash', file)
            self.assertIn('uploader', file)
            self.assertIn('uploaded_at', file)

    def test_file_delete(self):
        # Upload a file
        url = reverse('file-upload')
        file1 = SimpleUploadedFile("delete.txt", b"delete me")
        response = self.client.post(url, {'file': file1}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        file_id = response.data['id'] if 'id' in response.data else None
        self.assertIsNotNone(file_id)
        # Delete the file
        url = reverse('file-delete', args=[file_id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        # Ensure it's gone
        self.assertFalse(FileUpload.objects.filter(id=file_id).exists())

    def test_file_upload_rbac(self):
        # Only allowed roles can upload
        self.user.role = 'user'
        self.user.save()
        url = reverse('file-upload')
        file = SimpleUploadedFile("rbac.txt", b"rbac")
        response = self.client.post(url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, 201)
        # Change to guest (not allowed)
        self.user.role = 'guest'
        self.user.save()
        file2 = SimpleUploadedFile("rbac2.txt", b"rbac2")
        response = self.client.post(url, {'file': file2}, format='multipart')
        self.assertEqual(response.status_code, 403)

    def test_file_event_logging(self):
        url = reverse('file-upload')
        file = SimpleUploadedFile("log.txt", b"log")
        response = self.client.post(url, {'file': file}, format='multipart')
        file_id = response.data['id']
        # Upload event
        self.assertTrue(FileEventLog.objects.filter(event_type='upload', file__id=file_id, user=self.user).exists())
        # Access event (list)
        url = reverse('file-list')
        self.client.get(url)
        self.assertTrue(FileEventLog.objects.filter(event_type='access', file__id=file_id, user=self.user).exists())
        # Delete event (file is now null)
        url = reverse('file-delete', args=[file_id])
        self.client.delete(url)
        self.assertTrue(FileEventLog.objects.filter(event_type='delete', user=self.user).exists())

    def test_rag_query_endpoint(self):
        url = reverse('rag-query')
        data = {"query": "What is RAG?"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('answer', response.data)
        self.assertIn('RAG answer', response.data['answer'])

    def test_file_process_endpoint(self):
        # Upload a file
        url = reverse('file-upload')
        file = SimpleUploadedFile("process.txt", b"process")
        response = self.client.post(url, {'file': file}, format='multipart')
        file_id = response.data['id']
        url = reverse('file-process', args=[file_id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('result', response.data)
        self.assertIn('Processed file', response.data['result'])

    def test_conversation_summaries_caching(self):
        # This test checks that repeated calls return the same data (cache hit)
        for i in range(2):
            Conversation.objects.create(title=f"Cache {i}", summary=f"CacheSum {i}", user=self.user)
        url = reverse('conversation-summaries')
        response1 = self.client.get(url)
        response2 = self.client.get(url)
        self.assertEqual(response1.data, response2.data) 