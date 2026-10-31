import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "savevideokit_cli", ROOT / "cli" / "savevideokit_cli.py"
)
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


def fake_download(url, destination, timeout=180, referer=""):
    Path(destination).write_bytes(b"video-bytes")
    return 11, 11


class DirectClient:
    def __init__(self):
        self.created = False

    def inspect(self, url):
        return {
            "structuredContent": {
                "title": "direct case",
                "webpage_url": url,
                "direct_options": [
                    {
                        "download_url": "https://cdn.example/video",
                        "ext": "mp4",
                        "height": 720,
                        "filesize": 11,
                    }
                ],
            }
        }

    def create(self, *args, **kwargs):
        self.created = True
        raise AssertionError("a direct option must not create a cloud job")


class RelayClient:
    def __init__(self):
        self.created = False
        self.status_calls = 0

    def inspect(self, url):
        return {
            "structuredContent": {
                "title": "relay case",
                "webpage_url": url,
                "direct_download_available": False,
                "direct_options": [],
                "formats": [
                    {
                        "ext": "mp4",
                        "direct_eligible": False,
                        "direct_reason": "no_audio",
                    }
                ],
            }
        }

    def create(self, url, fmt="mp4", quality=""):
        self.created = True
        return {"structuredContent": {"job_id": "job-1"}}

    def status(self, job_id):
        self.status_calls += 1
        return {
            "structuredContent": {
                "status": "success",
                "download_url": "https://cloud.example/merged.mp4",
            }
        }


class RoutingTests(unittest.TestCase):
    @patch.object(CLI, "_download_file", fake_download)
    def test_direct_option_never_creates_job(self):
        client = DirectClient()
        with tempfile.TemporaryDirectory() as output:
            with redirect_stdout(io.StringIO()):
                CLI.cmd_download(client, "https://example/direct", "mp4", "", output, 0, 2)
            self.assertFalse(client.created)
            self.assertEqual((Path(output) / "direct case.mp4").read_bytes(), b"video-bytes")

    @patch.object(CLI.time, "sleep", lambda _: None)
    @patch.object(CLI, "_download_file", fake_download)
    def test_no_audio_direct_option_uses_cloud_job(self):
        client = RelayClient()
        with tempfile.TemporaryDirectory() as output:
            with redirect_stdout(io.StringIO()):
                CLI.cmd_download(client, "https://example/relay", "mp4", "", output, 0, 2)
            self.assertTrue(client.created)
            self.assertEqual(client.status_calls, 1)
            self.assertEqual((Path(output) / "relay case.mp4").read_bytes(), b"video-bytes")


if __name__ == "__main__":
    unittest.main()
