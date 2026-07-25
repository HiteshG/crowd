from __future__ import annotations

import hashlib
import re

from .models import Beat, Episode


def parse_episodes(story_text: str, mode: str = "headings") -> list[Episode]:
    """Parse markdown/plain text into episodes and beat maps."""
    if mode == "separator":
        return parse_separator_episodes(story_text)
    if mode != "headings":
        raise ValueError(f"Unknown episode parse mode: {mode}")

    story_text = strip_fixture_notes(story_text)
    heading = re.compile(
        r"^\s{0,3}(?:#{1,6}\s*)?.*\b(?:episode|ep)\b\s*(\d+)\b[:.\-\s]*(.*)$",
        re.IGNORECASE,
    )
    chunks: list[tuple[int, str, str]] = []
    current_no: int | None = None
    current_title = ""
    current_lines: list[str] = []

    for line in story_text.splitlines():
        match = heading.match(line)
        if match:
            if current_no is not None:
                chunks.append((current_no, current_title, clean_episode_text("\n".join(current_lines))))
            current_no = int(match.group(1))
            current_title = match.group(2).strip() or f"Episode {current_no}"
            current_lines = []
        else:
            current_lines.append(line)

    if current_no is not None:
        chunks.append((current_no, current_title, clean_episode_text("\n".join(current_lines))))

    if not chunks and story_text.strip():
        chunks = [(1, "Episode 1", clean_episode_text(story_text))]

    return [
        Episode(episode_no=no, title=title, text=text, beats=make_beats(no, text))
        for no, title, text in chunks
        if text
    ]


def parse_separator_episodes(story_text: str) -> list[Episode]:
    chunks = [part.strip() for part in re.split(r"\n\s*---+\s*\n", story_text) if part.strip()]
    episodes: list[Episode] = []
    for idx, chunk in enumerate(chunks, 1):
        title = title_from_chunk(chunk, idx)
        text = clean_episode_text(chunk)
        episodes.append(
            Episode(
                episode_no=idx,
                title=title,
                text=text,
                beats=make_beats(idx, text),
            )
        )
    return episodes


def title_from_chunk(chunk: str, idx: int) -> str:
    for line in chunk.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        heading = re.match(r"^#{1,6}\s*(.+)$", stripped)
        if heading:
            value = heading.group(1).strip()
            episode = re.search(r"\bEpisode\s+\d+\s*[:\-—]?\s*(.*)$", value, re.IGNORECASE)
            if episode:
                return episode.group(1).strip() or value
            return value
        bold = re.match(r"^\*\*(.+?)\*\*$", stripped)
        if bold:
            return bold.group(1).strip()
        return f"Episode {idx}"
    return f"Episode {idx}"


def strip_fixture_notes(story_text: str) -> str:
    lines: list[str] = []
    for line in story_text.splitlines():
        stripped = line.strip()
        if re.match(r"^##\s+TEST-HARNESS NOTES\b", stripped, re.IGNORECASE):
            break
        if re.match(r"^##\s+Using the pair\b", stripped, re.IGNORECASE):
            break
        if stripped == "— END OF SCRIPT —":
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def clean_episode_text(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("###"):
            continue
        if re.match(r"^-{3,}$", stripped):
            continue
        if re.match(r"^>\s*\[B\d+", stripped, re.IGNORECASE):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def make_beats(episode_no: int, text: str) -> list[Beat]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(paragraphs) < 3:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        paragraphs = [
            " ".join(sentences[idx : idx + 4]).strip()
            for idx in range(0, len(sentences), 4)
            if " ".join(sentences[idx : idx + 4]).strip()
        ]
    return [
        Beat(beat_id=f"s{episode_no:03d}_b{idx + 1:02d}", text=paragraph)
        for idx, paragraph in enumerate(paragraphs)
    ]


def story_version(episodes: list[Episode]) -> str:
    digest = hashlib.sha256()
    for episode in episodes:
        digest.update(str(episode.episode_no).encode("utf-8"))
        digest.update(episode.title.encode("utf-8"))
        digest.update(episode.text.encode("utf-8"))
    return digest.hexdigest()[:16]


def format_beat_map(episode: Episode) -> str:
    lines: list[str] = []
    for beat in episode.beats:
        excerpt = re.sub(r"\s+", " ", beat.text).strip()
        if len(excerpt) > 220:
            excerpt = excerpt[:217] + "..."
        lines.append(f"- {beat.beat_id}: {excerpt}")
    return "\n".join(lines)
