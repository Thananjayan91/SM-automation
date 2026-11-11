"""Tests for AI pipeline, research extraction, and async generation jobs (Milestone 3)."""
import pytest
from app.extensions import db
from app.models.research import GenerationJob, JobStatus, JobStep, ResearchRun
from app.models.source import Source, SourceType
from app.models.post import Post
from app.models.media_asset import MediaAsset
from app.models.usage_event import UsageEvent, UsageEventType
from app.services.ai import (
    MockResearchProvider,
    MockTextProvider,
    MockImageProvider,
)
from app.tasks.generation import execute_generation_job


def test_mock_research_provider():
    provider = MockResearchProvider()
    res = provider.research("Organic Growth Strategies")
    assert res.summary is not None
    assert len(res.citations) >= 1
    assert res.tokens_used > 0
    assert res.cost_usd > 0


def test_mock_text_provider():
    provider = MockTextProvider()
    res = provider.generate_caption("AI in Marketing", tone="playful")
    assert "AI in Marketing" in res.caption
    assert len(res.hashtags) >= 2
    assert all(tag.startswith("#") for tag in res.hashtags)
    assert res.tokens_used > 0


def test_mock_image_provider():
    provider = MockImageProvider()
    res = provider.generate_image("Modern Social Banner", style="modern")
    assert res.image_bytes is not None
    assert len(res.image_bytes) > 1000
    assert res.mime_type == "image/png"


def test_execute_generation_job_end_to_end(app, client, tenant_a, user_a):
    with app.app_context():
        # Create a source
        source = Source(
            tenant_id=tenant_a.id,
            source_type=SourceType.MANUAL,
            headline="Next-gen Automation Tools",
            raw_text="Key developments in automated social workflows.",
        )
        db.session.add(source)
        db.session.flush()

        # Create job
        job = GenerationJob(
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            source_id=source.id,
            status=JobStatus.PENDING,
            current_step=JobStep.EXTRACTING,
            progress_pct=10,
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id

        # Execute pipeline
        completed_job = execute_generation_job(job_id)
        assert completed_job.status == JobStatus.SUCCESS
        assert completed_job.progress_pct == 100
        assert completed_job.current_step == JobStep.COMPLETED
        assert completed_job.post_id is not None

        # Verify post created and media linked
        post = db.session.get(Post, completed_job.post_id)
        assert post is not None
        assert post.tenant_id == tenant_a.id
        assert len(post.media_links) == 1
        assert "Automation" in post.caption or len(post.caption) > 10

        # Verify research run and citations saved
        research_run = ResearchRun.query.filter_by(source_id=source.id).first()
        assert research_run is not None
        assert len(research_run.citations) > 0

        # Verify usage events recorded
        events = UsageEvent.query.filter_by(tenant_id=tenant_a.id).all()
        assert len(events) >= 2  # Tokens + Image


def test_api_generation_endpoints(app, client, tenant_a, user_a):
    # Log in
    with client.session_transaction() as sess:
        sess["_user_id"] = user_a.id
        sess["active_tenant_id"] = tenant_a.id

    # POST /api/v1/posts/generate
    resp = client.post(
        "/api/v1/posts/generate",
        json={"topic": "Trends in Distributed Systems"},
        headers={"X-Tenant-ID": tenant_a.id},
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "id" in data
    job_id = data["id"]

    # GET /api/v1/jobs/<id>
    get_resp = client.get(f"/api/v1/jobs/{job_id}", headers={"X-Tenant-ID": tenant_a.id})
    assert get_resp.status_code == 200
    job_data = get_resp.get_json()
    assert job_data["id"] == job_id
    assert job_data["status"] in ["pending", "processing", "success"]


def test_tenant_isolation_on_jobs(app, client, tenant_a, user_a, tenant_b):
    with app.app_context():
        job = GenerationJob(
            tenant_id=tenant_b.id,
            status=JobStatus.PENDING,
            current_step=JobStep.EXTRACTING,
        )
        db.session.add(job)
        db.session.commit()
        other_job_id = job.id

    # Log in as user_a who belongs to tenant_a, NOT tenant_b
    with client.session_transaction() as sess:
        sess["_user_id"] = user_a.id
        sess["active_tenant_id"] = tenant_a.id

    resp = client.get(f"/api/v1/jobs/{other_job_id}", headers={"X-Tenant-ID": tenant_a.id})
    assert resp.status_code == 404


def test_multilingual_caption_generation(app, client, tenant_a, user_a):
    provider = MockTextProvider()
    ta = provider.generate_caption("Vivo X200", language="tamil")
    assert "முக்கிய தகவல்கள்" in ta.caption
    assert "#தமிழ்" in ta.hashtags

    si = provider.generate_caption("Vivo X200", language="sinhala")
    assert "නවතම තොරතුරු" in si.caption
    assert "#සිංහල" in si.hashtags

    with client.session_transaction() as sess:
        sess["_user_id"] = user_a.id
        sess["active_tenant_id"] = tenant_a.id

    resp = client.post(
        "/api/v1/posts/generate",
        json={"topic": "Jaffna Tech Summit", "language": "tamil", "tone": "engaging"},
        headers={"X-Tenant-ID": tenant_a.id},
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["post_id"] is not None

    with app.app_context():
        from app.models import Post
        post = db.session.get(Post, data["post_id"])
        assert "Jaffna Tech Summit" in post.caption
        assert "பகிருங்கள்" in post.caption


def test_pexels_image_provider_and_import_endpoint(app, client, tenant_a, user_a, monkeypatch):
    import io
    from PIL import Image
    from unittest.mock import patch, MagicMock
    from app.services.ai.image_provider import PexelsImageProvider

    img_buf = io.BytesIO()
    Image.new("RGB", (200, 200), color="teal").save(img_buf, format="JPEG")
    sample_jpg_bytes = img_buf.getvalue()

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {
        "photos": [
            {
                "id": 42,
                "alt": "Vivo smartphone on desk",
                "photographer": "Jane Doe",
                "src": {
                    "medium": "https://images.pexels.com/photos/42/medium.jpg",
                    "large": "https://images.pexels.com/photos/42/large.jpg",
                },
            }
        ]
    }

    dl_resp = MagicMock()
    dl_resp.status_code = 200
    dl_resp.content = sample_jpg_bytes
    dl_resp.headers = {"Content-Type": "image/jpeg"}

    with patch("requests.get", side_effect=[search_resp, dl_resp]):
        provider = PexelsImageProvider(api_key="test_pexels_key")
        res = provider.generate_image("Vivo smartphones launch!")
        assert res.mime_type == "image/jpeg"
        assert res.cost_usd == 0.0
        assert res.image_bytes == sample_jpg_bytes

    monkeypatch.setenv("PEXELS_API_KEY", "test_pexels_key")
    with client.session_transaction() as sess:
        sess["_user_id"] = user_a.id
        sess["active_tenant_id"] = tenant_a.id

    with patch("requests.get", return_value=search_resp):
        r_search = client.get("/api/v1/media/pexels-search?q=smartphone")
        assert r_search.status_code == 200
        photos = r_search.get_json()["photos"]
        assert len(photos) == 1
        assert photos[0]["full"] == "https://images.pexels.com/photos/42/large.jpg"

    # SSRF guard: reject non-Pexels host
    r_bad = client.post("/api/v1/media/import-url", json={"url": "https://evil.com/x.jpg"})
    assert r_bad.status_code == 400

    with patch("requests.get", return_value=dl_resp):
        r_import = client.post(
            "/api/v1/media/import-url",
            json={"url": "https://images.pexels.com/photos/42/large.jpg", "alt": "Vivo phone"},
        )
        assert r_import.status_code == 201
        assert "id" in r_import.get_json()


