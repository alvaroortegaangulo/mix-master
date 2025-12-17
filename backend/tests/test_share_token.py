import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from src.utils import job_store

class TestJobStore(unittest.TestCase):
    @patch('src.utils.job_store._get_redis_client')
    def test_set_share_token_success(self, mock_get_client):
        mock_redis = MagicMock()
        mock_get_client.return_value = mock_redis

        token = "test_token"
        job_id = "test_job_id"

        result = job_store.set_share_token(token, job_id)

        self.assertTrue(result)
        mock_redis.setex.assert_called_with(f"share_token:{token}", 7 * 24 * 3600, job_id)

    @patch('src.utils.job_store._get_redis_client')
    def test_set_share_token_no_redis(self, mock_get_client):
        mock_get_client.return_value = None
        result = job_store.set_share_token("t", "j")
        self.assertFalse(result)

    @patch('src.utils.job_store._get_redis_client')
    def test_get_job_id_success(self, mock_get_client):
        mock_redis = MagicMock()
        mock_get_client.return_value = mock_redis
        mock_redis.get.return_value = b"test_job_id"

        token = "test_token"
        result = job_store.get_job_id_from_share_token(token)

        self.assertEqual(result, "test_job_id")
        mock_redis.get.assert_called_with(f"share_token:{token}")

    @patch('src.utils.job_store._get_redis_client')
    def test_get_job_id_not_found(self, mock_get_client):
        mock_redis = MagicMock()
        mock_get_client.return_value = mock_redis
        mock_redis.get.return_value = None

        result = job_store.get_job_id_from_share_token("invalid_token")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
