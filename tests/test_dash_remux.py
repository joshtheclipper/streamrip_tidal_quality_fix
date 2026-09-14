"""The DASH remux must not depend on asyncio subprocess support.

On Windows streamrip uses the selector event loop (aiodns requires it), and
that loop cannot start subprocesses, so asyncio.create_subprocess_exec fails
before ffmpeg runs. The remux runs ffmpeg in a thread instead.
"""

import os
import shutil
import subprocess
from unittest.mock import patch

import pytest

from streamrip.client.downloadable import _remux_to_flac
from streamrip.exceptions import NonStreamableError

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


@pytest.fixture
def fmp4(tmp_path):
    """A fragmented MP4 holding FLAC, the shape of a Tidal DASH download."""
    src = tmp_path / "track.flac.tmp.mp4"
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=48000",
            "-c:a", "flac", "-strict", "-2",
            "-f", "mp4", "-movflags", "frag_keyframe+empty_moov",
            "-y", str(src),
        ],
        check=True,
    )
    return src


def _no_async_subprocess(*args, **kwargs):
    raise NotImplementedError("selector event loop cannot start subprocesses")


@pytest.mark.asyncio
async def test_remux_works_without_asyncio_subprocesses(fmp4):
    out = str(fmp4)[: -len(".tmp.mp4")]
    with patch("asyncio.create_subprocess_exec", _no_async_subprocess):
        await _remux_to_flac(str(fmp4), out)
    assert os.path.isfile(out)
    assert not fmp4.exists()


@pytest.mark.asyncio
async def test_failed_remux_raises_and_cleans_up(tmp_path):
    bad = tmp_path / "bad.flac.tmp.mp4"
    bad.write_bytes(b"not audio")
    with pytest.raises(NonStreamableError):
        await _remux_to_flac(str(bad), str(tmp_path / "bad.flac"))
    assert not bad.exists()
