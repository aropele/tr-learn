# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import re
import unicodedata

STOPWORDS = {"a", "an", "the", "of", "for", "and"}
MAX_SLUG = 70
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
PUBLISHED_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def slugify(title: str) -> str:
    text = title.replace("'", "").replace("’", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    words = [w for w in text.split("-") if w and w not in STOPWORDS]
    out = []
    for w in words:
        if len("-".join(out + [w])) > MAX_SLUG:
            break
        out.append(w)
    slug = "-".join(out) or (words[0][:MAX_SLUG] if words else "")
    if not slug:
        raise ValueError(f"title yields empty slug: {title!r}")
    return slug


def date_part(published: str | None, fetch_date: str) -> str:
    if published is None:
        return fetch_date
    if not PUBLISHED_RE.match(published):
        raise ValueError(f"invalid published date: {published!r}")
    parts = published.split("-")
    return "-".join(parts + ["00"] * (3 - len(parts)))


def make_id(title: str, published: str | None, fetch_date: str) -> str:
    return f"{date_part(published, fetch_date)}-{slugify(title)}"
