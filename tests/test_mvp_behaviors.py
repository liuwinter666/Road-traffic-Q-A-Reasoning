"""Danh sách hành vi MVP phải trỏ đúng tới điều khoản còn hiệu lực, có chứa cụm từ kiểm chứng."""

from src.ingest import mvp_report


def test_mvp_behaviors_valid():
    assert mvp_report.main() == 0
