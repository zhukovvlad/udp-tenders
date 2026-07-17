"""Unit-тесты async-обёрток S3 (S0-6): sync-boto3 уходит в поток, не блокирует loop."""
import pytest


@pytest.mark.asyncio
async def test_download_file_async_delegates(monkeypatch):
    """download_file_async возвращает то же, что sync download_file."""
    import s3

    monkeypatch.setattr(s3, "download_file", lambda name: b"bytes-for-" + name.encode())
    result = await s3.download_file_async("k/x.pdf")
    assert result == b"bytes-for-k/x.pdf"


@pytest.mark.asyncio
async def test_upload_file_async_delegates(monkeypatch):
    """upload_file_async возвращает ключ, как sync upload_file."""
    import s3

    monkeypatch.setattr(s3, "upload_file", lambda b, name: name)
    assert await s3.upload_file_async(b"data", "k/y.pdf") == "k/y.pdf"
