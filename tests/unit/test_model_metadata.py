from sqlalchemy import Text

from apps.src.models.issue_docent import IssueDocent
from apps.src.models.stock_term import StockTerm


def test_issue_docent_summary_uses_text_column():
    assert isinstance(IssueDocent.__table__.c.summary.type, Text)


def test_stock_term_timestamps_keep_timezone_information():
    assert StockTerm.__table__.c.created_at.type.timezone is True
    assert StockTerm.__table__.c.updated_at.type.timezone is True
