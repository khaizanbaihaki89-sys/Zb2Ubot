"""Downloader terbatas untuk TikTok, Instagram, dan Telegram Private."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse


class DownloaderError(Exception):
    """Kesalahan yang aman ditampilkan sebagai feedback command."""


class UnsupportedLink(DownloaderError):
    """URL bukan salah satu layanan yang diizinkan."""


class PrivateMessageAccessError(DownloaderError):
    """Akun Userbot tidak dapat mengakses pesan private tersebut."""


_SOCIAL_HOSTS = {
    "tiktok": {"tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"},
    "instagram": {"instagram.com", "www.instagram.com", "instagr.am", "www.instagr.am"},
}
_VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".avi"}


def _validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UnsupportedLink("URL harus diawali http:// atau https://.")
    return url.strip()


def social_service(url: str) -> str:
    """Kembalikan layanan sosial yang diizinkan untuk URL."""
    url = _validate_url(url)
    hostname = (urlparse(url).hostname or "").casefold()
    for service, hosts in _SOCIAL_HOSTS.items():
        if hostname in hosts or any(hostname.endswith(f".{host}") for host in hosts):
            return service
    raise UnsupportedLink("Hanya link TikTok dan Instagram yang didukung.")


def _find_downloaded_file(directory: Path) -> Path:
    candidates = [
        path
        for path in directory.rglob("*")
        if path.is_file()
        and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        raise DownloaderError("File hasil download tidak ditemukan.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _download_social_sync(url: str, service: str, directory: Path) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:
        raise DownloaderError(
            "Modul downloader belum tersedia. Instal dependency yt-dlp terlebih dahulu."
        ) from exc

    output = str(directory / "%(id)s.%(ext)s")
    options = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([url])
    except Exception as exc:
        raise DownloaderError(f"Gagal mengunduh {service.title()}: {exc}") from exc
    return _find_downloaded_file(directory)


async def download_social(url: str, service: str) -> tuple[Path, tempfile.TemporaryDirectory]:
    """Download URL sosial ke direktori sementara dan kembalikan file-nya."""
    import asyncio

    detected = social_service(url)
    if detected != service:
        raise UnsupportedLink(f"Gunakan link {service.title()} untuk command ini.")

    temporary = tempfile.TemporaryDirectory(prefix=f"ibeks_{service}_")
    directory = Path(temporary.name)
    try:
        path = await asyncio.to_thread(_download_social_sync, url, service, directory)
    except Exception:
        temporary.cleanup()
        raise
    return path, temporary


def _telegram_target(url: str) -> tuple[str, int | str, int] | tuple[str, str, None]:
    """Parse link t.me/c, t.me/username/id, atau invite/id."""
    parsed = urlparse(_validate_url(url))
    if (parsed.hostname or "").casefold() not in {"t.me", "www.t.me", "telegram.me"}:
        raise UnsupportedLink("Gunakan link Telegram yang valid.")

    parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 2 and parts[0] == "c" and parts[1].isdigit():
        if len(parts) < 3 or not parts[2].isdigit():
            raise UnsupportedLink("Link Telegram tidak memiliki ID pesan.")
        channel_id = parts[1]
        chat_id = -(100 * (10 ** len(channel_id)) + int(channel_id))
        return "chat_id", chat_id, int(parts[2])

    if parts and parts[0].startswith("+"):
        invite = parts[0][1:]
        if len(parts) < 2 or not parts[1].isdigit():
            return "invite", invite, None
        return "invite", invite, int(parts[1])

    if len(parts) >= 2 and parts[1].isdigit():
        return "username", parts[0], int(parts[1])

    raise UnsupportedLink("Link Telegram harus menunjuk ke pesan tertentu.")


async def download_telegram_media(client, url: str, directory: Path) -> Path:
    """Ambil media dari pesan Telegram yang dapat diakses akun Userbot."""
    kind, target, message_id = _telegram_target(url)
    if message_id is None:
        raise UnsupportedLink(
            "Link undangan Telegram tidak menunjuk ke pesan media tertentu."
        )

    try:
        if kind == "invite":
            chat = await client.join_chat(f"https://t.me/+{target}")
            target = chat.id
        message = await client.get_messages(target, message_id)
    except Exception as exc:
        raise PrivateMessageAccessError(
            "Tidak memiliki akses ke pesan tersebut."
        ) from exc

    if not message or getattr(message, "empty", False) or not message.media:
        raise PrivateMessageAccessError("Tidak memiliki akses ke pesan tersebut.")

    try:
        result = await client.download_media(
            message,
            file_name=str(directory / "telegram_media"),
        )
    except Exception as exc:
        raise PrivateMessageAccessError(
            "Tidak memiliki akses ke pesan tersebut."
        ) from exc

    if not result:
        raise DownloaderError("Media Telegram tidak dapat diunduh.")
    return Path(result)


def is_video_file(path: Path) -> bool:
    return path.suffix.casefold() in _VIDEO_SUFFIXES