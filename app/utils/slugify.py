import re
import unicodedata


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def unique_slug(base_value: str, model, slug_field="slug", exclude_id=None):
    base = slugify(base_value) or "item"
    slug = base
    counter = 2
    while True:
        query = model.query.filter(getattr(model, slug_field) == slug)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base}-{counter}"
        counter += 1
