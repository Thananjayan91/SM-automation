"""Background and asynchronous generation tasks."""
import logging
from typing import Optional

from ..extensions import db
from ..models import (
    GenerationJob,
    JobStatus,
    JobStep,
    Source,
    SourceType,
    Post,
    MediaAsset,
    MediaSourceType,
    UsageEvent,
    UsageEventType,
    ResearchRun,
    ResearchCitation,
)
from ..services.ai import (
    get_research_provider,
    get_text_provider,
    get_image_provider,
)
from ..services.content_service import create_draft_post, update_post_content
from ..services.media_service import save_media_file

logger = logging.getLogger(__name__)


def execute_generation_job(job_id: str) -> GenerationJob:
    """Execute the end-to-end AI generation pipeline for a job.
    
    Can run directly or inside a Celery worker.
    """
    job = db.session.get(GenerationJob, job_id)
    if not job:
        raise ValueError(f"GenerationJob {job_id} not found")

    try:
        job.status = JobStatus.PROCESSING
        job.current_step = JobStep.EXTRACTING
        job.progress_pct = 15
        job.error_message = None
        job.error_code = None
        db.session.commit()

        # 1. Source extraction & topic determination
        topic = "Strategic Business Trends & Innovation"
        source_url = None
        source_obj = None

        if job.source_id:
            source_obj = db.session.get(Source, job.source_id)
            if source_obj:
                topic = source_obj.headline or source_obj.raw_text or "Industry Insights"
                if source_obj.source_type == SourceType.URL and source_obj.source_url:
                    source_url = source_obj.source_url
        elif job.post_id:
            post_obj = db.session.get(Post, job.post_id)
            if post_obj and post_obj.current_version:
                topic = post_obj.current_version.caption[:100]

        # 2. Research & fact-checking
        job.current_step = JobStep.RESEARCHING
        job.progress_pct = 40
        db.session.commit()

        research_provider = get_research_provider()
        res_result = research_provider.research(topic=topic, source_url=source_url)

        # Save research run and citations if source is attached
        if job.source_id:
            research_run = ResearchRun(
                tenant_id=job.tenant_id,
                source_id=job.source_id,
                provider=type(research_provider).__name__,
                status="success",
                summary=res_result.summary,
                result_json=res_result.metadata,
            )
            db.session.add(research_run)
            db.session.flush()

            for cit in res_result.citations:
                citation_record = ResearchCitation(
                    tenant_id=job.tenant_id,
                    research_run_id=research_run.id,
                    url=cit.url,
                    title=cit.title,
                    excerpt=cit.excerpt,
                    published_at=cit.published_at,
                )
                db.session.add(citation_record)

        if res_result.tokens_used:
            db.session.add(
                UsageEvent(
                    tenant_id=job.tenant_id,
                    user_id=job.user_id,
                    event_type=UsageEventType.RESEARCH,
                    input_units=res_result.tokens_used,
                    estimated_cost_cents=int(res_result.cost_usd * 100),
                    status="success",
                )
            )
        db.session.commit()

        # 3. Caption and hashtag generation
        job.current_step = JobStep.WRITING
        job.progress_pct = 70
        db.session.commit()

        tone = "professional"
        language = "english"
        if source_obj and source_obj.tone_instruction:
            raw_inst = source_obj.tone_instruction
            if "language=" in raw_inst or "tone=" in raw_inst:
                for part in raw_inst.split(";"):
                    if part.startswith("language="):
                        language = part.split("=", 1)[1].strip() or "english"
                    elif part.startswith("tone="):
                        tone = part.split("=", 1)[1].strip() or "professional"
            else:
                tone = raw_inst

        text_provider = get_text_provider()
        caption_result = text_provider.generate_caption(
            topic=topic,
            research_summary=res_result.summary,
            tone=tone,
            language=language,
        )

        if caption_result.tokens_used:
            db.session.add(
                UsageEvent(
                    tenant_id=job.tenant_id,
                    user_id=job.user_id,
                    event_type=UsageEventType.AI_TEXT_GENERATION,
                    output_units=caption_result.tokens_used,
                    estimated_cost_cents=int(caption_result.cost_usd * 100),
                    status="success",
                )
            )
        db.session.commit()

        # 4. Branded image generation (preserve existing uploaded media if already attached)
        job.current_step = JobStep.IMAGE_GENERATION
        job.progress_pct = 90
        db.session.commit()

        preserved_media_ids = None
        if job.post_id:
            existing_post = db.session.get(Post, job.post_id)
            if existing_post and existing_post.media_links:
                uploaded_links = [
                    ml.media_asset_id
                    for ml in sorted(existing_post.media_links, key=lambda x: x.position)
                    if ml.media_asset and ml.media_asset.source_type == MediaSourceType.UPLOADED
                ]
                if uploaded_links:
                    preserved_media_ids = [ml.media_asset_id for ml in sorted(existing_post.media_links, key=lambda x: x.position)]

        if preserved_media_ids is not None:
            final_media_ids = preserved_media_ids
        else:
            image_provider = get_image_provider()
            img_result = image_provider.generate_image(prompt=topic, style="modern")

            # Store generated image in tenant storage
            import io
            from werkzeug.datastructures import FileStorage

            fs = FileStorage(
                stream=io.BytesIO(img_result.image_bytes),
                filename=f"ai_gen_{job.id[:8]}.png",
                content_type=img_result.mime_type,
            )
            media_asset, err = save_media_file(
                file_storage=fs,
                tenant_id=job.tenant_id,
                user_id=job.user_id,
                source_type=MediaSourceType.AI_GENERATED,
                labels=["ai-generated", "social-banner"],
            )
            if err:
                raise RuntimeError(f"Failed to save generated media: {err}")

            db.session.add(
                UsageEvent(
                    tenant_id=job.tenant_id,
                    user_id=job.user_id,
                    event_type=UsageEventType.IMAGE_GENERATION,
                    image_count=1,
                    estimated_cost_cents=int(img_result.cost_usd * 100),
                    status="success",
                )
            )
            db.session.commit()
            final_media_ids = [media_asset.id]

        # 5. Create or update Post draft
        if not job.post_id:
            post, err = create_draft_post(
                tenant_id=job.tenant_id,
                user_id=job.user_id or "",
                caption=caption_result.caption,
                hashtags=caption_result.hashtags,
                media_asset_ids=final_media_ids,
                source_id=job.source_id,
            )
            if err:
                raise RuntimeError(f"Failed to create draft post: {err}")
            job.post_id = post.id
        else:
            post, err = update_post_content(
                post_id=job.post_id,
                tenant_id=job.tenant_id,
                user_id=job.user_id or "",
                caption=caption_result.caption,
                hashtags=caption_result.hashtags,
                media_asset_ids=final_media_ids,
            )
            if err:
                raise RuntimeError(f"Failed to update post content: {err}")

        job.status = JobStatus.SUCCESS
        job.current_step = JobStep.COMPLETED
        job.progress_pct = 100
        db.session.commit()
        return job

    except Exception as exc:
        db.session.rollback()
        logger.exception(f"Error executing generation job {job_id}: {exc}")
        # Re-fetch fresh job reference
        job = db.session.get(GenerationJob, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.current_step = JobStep.FAILED
            job.error_message = str(exc)
            job.error_code = type(exc).__name__
            db.session.commit()
        raise exc


def dispatch_generation_job(job_id: str, async_mode: bool = True) -> str:
    """Dispatches generation task to Celery or falls back to inline execution."""
    if async_mode:
        try:
            from worker import celery
            task = celery.send_task("tasks.run_generation", args=[job_id])
            return task.id
        except Exception as e:
            logger.info(f"Celery dispatch failed or Redis unavailable ({e}); running inline.")

    execute_generation_job(job_id)
    return job_id
