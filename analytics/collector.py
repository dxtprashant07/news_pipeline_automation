"""
Stage 7 — Analytics Collector.

Pulls performance data from Google Analytics 4 (GA4) and Google Search Console
for published articles and stores snapshots in the analytics_snapshots table.

Requires:
  - GA4_PROPERTY_ID in .env
  - GOOGLE_SERVICE_ACCOUNT_JSON path to a service account key file
  - google-analytics-data and google-search-console Python packages
"""
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select

from core.db.models import PublishedArticle, AnalyticsSnapshot
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("analytics.collector")


class AnalyticsCollector:
    def __init__(self, session: Session) -> None:
        self.session  = session
        self.settings = get_settings()

    def collect(self) -> dict:
        """
        Fetch analytics for all published articles from the last 30 days
        and store snapshots. Returns a summary dict.
        """
        if not self.settings.ga4_property_id or not self.settings.google_service_account_json:
            logger.info("GA4 not configured (GA4_PROPERTY_ID / GOOGLE_SERVICE_ACCOUNT_JSON) — skipping analytics collection")
            return {"collected": 0, "skipped": True}

        published = self.session.scalars(select(PublishedArticle)).all()
        if not published:
            return {"collected": 0}

        collected = 0
        for article in published:
            try:
                metrics = self._fetch_ga4_metrics(article.wordpress_post_url)
                search  = self._fetch_search_console(article.wordpress_post_url)
                self._save_snapshot(article.id, metrics, search)
                collected += 1
            except Exception as exc:
                logger.warning(f"Analytics collection failed for article {article.id}: {exc!r}")

        logger.info(f"Analytics collected for {collected}/{len(published)} articles")
        return {"collected": collected}

    def _fetch_ga4_metrics(self, page_url: str) -> dict:
        """Fetch page_views, sessions, avg_time_on_page, bounce_rate from GA4."""
        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.analytics.data_v1beta.types import (
                RunReportRequest, Dimension, Metric, DateRange, FilterExpression, Filter
            )
            import google.oauth2.service_account as sa

            credentials = sa.Credentials.from_service_account_file(
                self.settings.google_service_account_json,
                scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            )
            client  = BetaAnalyticsDataClient(credentials=credentials)
            request = RunReportRequest(
                property=f"properties/{self.settings.ga4_property_id}",
                dimensions=[Dimension(name="pagePath")],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="sessions"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="bounceRate"),
                ],
                date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="pagePath",
                        string_filter=Filter.StringFilter(value=page_url, match_type="CONTAINS"),
                    )
                ),
            )
            response = client.run_report(request)
            if not response.rows:
                return {}
            row = response.rows[0].metric_values
            return {
                "page_views":       int(row[0].value or 0),
                "sessions":         int(row[1].value or 0),
                "avg_time_on_page": float(row[2].value or 0),
                "bounce_rate":      float(row[3].value or 0),
            }
        except ImportError:
            logger.warning("google-analytics-data not installed — install with: pip install google-analytics-data")
            return {}

    def _fetch_search_console(self, page_url: str) -> dict:
        """Fetch impressions, clicks, avg_position from Google Search Console."""
        try:
            from googleapiclient.discovery import build
            import google.oauth2.service_account as sa

            credentials = sa.Credentials.from_service_account_file(
                self.settings.google_service_account_json,
                scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
            )
            service = build("searchconsole", "v1", credentials=credentials)
            end_date   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_date = (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d")

            response = service.searchanalytics().query(
                siteUrl=self.settings.wordpress_url,
                body={
                    "startDate": start_date,
                    "endDate":   end_date,
                    "dimensions": ["page"],
                    "dimensionFilterGroups": [{
                        "filters": [{"dimension": "page", "expression": page_url}]
                    }],
                },
            ).execute()

            rows = response.get("rows", [])
            if not rows:
                return {}
            row = rows[0]
            return {
                "impressions":   row.get("impressions", 0),
                "clicks":        row.get("clicks", 0),
                "avg_position":  row.get("position", 0.0),
            }
        except ImportError:
            logger.warning("google-api-python-client not installed — install with: pip install google-api-python-client")
            return {}

    def _save_snapshot(self, published_id: int, ga4: dict, search: dict) -> None:
        performance_score = self._compute_performance_score(ga4, search)
        snapshot = AnalyticsSnapshot(
            published_id=published_id,
            snapshot_date=datetime.now(timezone.utc),
            page_views=ga4.get("page_views", 0),
            sessions=ga4.get("sessions", 0),
            avg_time_on_page=ga4.get("avg_time_on_page", 0.0),
            bounce_rate=ga4.get("bounce_rate", 0.0),
            impressions=search.get("impressions", 0),
            clicks=search.get("clicks", 0),
            avg_position=search.get("avg_position", 0.0),
            performance_score=performance_score,
        )
        self.session.add(snapshot)
        self.session.commit()

    def _compute_performance_score(self, ga4: dict, search: dict) -> float:
        """
        Composite score (0-100) fed back to the discovery priority scorer
        to up-rank categories and keywords that perform well.
        """
        views    = min(ga4.get("page_views", 0) / 1000, 1.0)
        clicks   = min(search.get("clicks", 0) / 500,  1.0)
        position = max(0.0, 1.0 - (search.get("avg_position", 100) / 100))
        bounce   = 1.0 - min(ga4.get("bounce_rate", 1.0), 1.0)

        score = (views * 0.35) + (clicks * 0.30) + (position * 0.20) + (bounce * 0.15)
        return round(score * 100, 2)
