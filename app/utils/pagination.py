from flask import request, current_app


def paginate_query(query, serializer=None):
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get("per_page", current_app.config["ITEMS_PER_PAGE"]))
    except ValueError:
        per_page = current_app.config["ITEMS_PER_PAGE"]
    per_page = min(max(per_page, 1), current_app.config["MAX_ITEMS_PER_PAGE"])

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items
    if serializer:
        items = [serializer(item) for item in items]

    return {
        "items": items,
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "total_pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }
