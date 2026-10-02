from .classify import load_taxonomy


def resolve(raw: str) -> set[str]:
    """Match user words like 'housing,climate' to taxonomy keys by prefix; unknown words raise."""
    tax = load_taxonomy()
    out = set()
    for word in (w.strip().lower() for w in raw.split(",") if w.strip()):
        hits = [k for k in tax if k.startswith(word) or word in k.split("_")]
        if not hits:
            raise ValueError(f"Unknown interest {word!r}. Choose from: {', '.join(tax)}")
        out.update(hits)
    return out
