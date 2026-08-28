from unittest.mock import patch


def test_run_crawler_requires_admin(client):
    resp = client.post("/api/admin/crawler/run", json={})
    assert resp.status_code == 401


def test_run_crawler_calls_service_and_returns_result(client, auth_header):
    fake_result = {"created": 2, "created_titles": ["A", "B"], "skipped_duplicate": 1, "errors": []}
    with patch("app.routes.admin.run_crawl", return_value=fake_result) as mock_run:
        resp = client.post("/api/admin/crawler/run", json={"max_items": 4}, headers=auth_header)

    assert resp.status_code == 200
    assert resp.get_json() == fake_result
    mock_run.assert_called_once_with(max_items=4)


def test_run_crawler_defaults_to_four_items(client, auth_header):
    with patch("app.routes.admin.run_crawl", return_value={"created": 0}) as mock_run:
        client.post("/api/admin/crawler/run", json={}, headers=auth_header)
    mock_run.assert_called_once_with(max_items=4)


def test_run_crawler_clamps_to_server_side_ceiling(client, auth_header):
    with patch("app.routes.admin.run_crawl", return_value={"created": 0}) as mock_run:
        client.post("/api/admin/crawler/run", json={"max_items": 999}, headers=auth_header)
    mock_run.assert_called_once_with(max_items=10)


def test_run_crawler_rejects_non_numeric_max_items_by_defaulting(client, auth_header):
    with patch("app.routes.admin.run_crawl", return_value={"created": 0}) as mock_run:
        client.post("/api/admin/crawler/run", json={"max_items": "not-a-number"}, headers=auth_header)
    mock_run.assert_called_once_with(max_items=4)
