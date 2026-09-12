from app.services import build_dashboard, ensure_demo_accounts
from app.database import build_session_factory


def test_build_dashboard_sums_accounts(tmp_path):
    session_factory = build_session_factory(str(tmp_path / "t.db"))
    with session_factory() as session:
        ensure_demo_accounts(session)
        data = build_dashboard(session)
    assert data["totals"]["accounts"] == 4
    assert data["totals"]["views"] == sum(a["total_views"] for a in data["accounts"])
