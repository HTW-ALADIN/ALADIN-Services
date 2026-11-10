import pytest

from config import settings
from core.download_service import BatchSizeError, validate_batch_size


def test_validate_batch_size_rejects_empty():
    with pytest.raises(BatchSizeError):
        validate_batch_size(0)


def test_validate_batch_size_rejects_over_limit():
    with pytest.raises(BatchSizeError):
        validate_batch_size(settings.download_max_batch_size + 1)


def test_validate_batch_size_accepts_within_limit():
    validate_batch_size(1)
    validate_batch_size(settings.download_max_batch_size)
