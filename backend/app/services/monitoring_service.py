"""
Automated satellite monitoring.

For every monitored property: look for Sentinel-2 passes newer than the latest stored snapshot,
download the best (least cloudy) one from the live provider, compare it with the previous snapshot using
the OpenCV pipeline, and - if the visual change score reaches MONITORING_ALERT_CHANGE_SCORE - create a
modification alert (status "New", needing human review) and notify the owner, reviewers and admins.

Never fabricates data: in live mode without credentials a run records a Failed status per property.
"""
import logging
import datetime
import smtplib
from email.message import EmailMessage
from typing import Dict, Any, List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (Property, PropertySnapshot, ImageAnalysis, Modification, MonitoringRun,
                        Notification, User, AuditLog)
from app.services.satellite_service import (satellite_service, SatelliteUnavailableError,
                                            SatelliteProviderError)
from app.services.cv_service import run_image_comparison_pipeline
from app.services.paths import snapshot_fs_path

logger = logging.getLogger(__name__)
_scheduler = None


def _next_alert_id(db: Session) -> str:
    year, n = datetime.datetime.utcnow().year, db.query(Modification).count()
    while True:
        n += 1
        cand = f"MOD-{year}-{n:04d}"
        if not db.query(Modification).filter(Modification.modification_alert_id == cand).first():
            return cand


def send_email(to: str, subject: str, body: str) -> bool:
    """Optional SMTP delivery; returns False (without raising) when SMTP is not configured or fails."""
    if not (settings.SMTP_HOST and settings.SMTP_FROM and to):
        return False
    try:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = settings.SMTP_FROM, to, subject
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("E-mail notification failed: %s", exc.__class__.__name__)
        return False


def _notify(db: Session, prop: Property, mod: Modification, score: float):
    recipients = {u.id: u for u in db.query(User).filter(User.role.in_(["admin", "reviewer"]), User.is_active == True).all()}  # noqa: E712
    if prop.owner_user_id:
        owner = db.query(User).filter(User.id == prop.owner_user_id).first()
        if owner:
            recipients[owner.id] = owner
    title = f"Possible property modification: {prop.property_reference}"
    msg = (f"Satellite monitoring found a visual change (score {score}) at {prop.address}. "
           f"Alert {mod.modification_alert_id} needs review. This is a signal, not proof of a modification.")
    for u in recipients.values():
        db.add(Notification(user_id=u.id, title=title, message=msg, type="MODIFICATION_ALERT",
                            link=f"/alerts/{mod.id}"))
        send_email(u.email, title, msg)


def check_property(db: Session, prop: Property) -> Dict[str, Any]:
    """Run one monitoring check; always records a MonitoringRun row."""
    run = MonitoringRun(property_id=prop.id, status="Completed", model_used="OpenCV Differencing")
    db.add(run)
    out = {"property_id": prop.id, "new_snapshot": False, "alert": None, "status": None, "message": ""}
    try:
        last = (db.query(PropertySnapshot).filter(PropertySnapshot.property_id == prop.id)
                .order_by(desc(PropertySnapshot.acquisition_date)).first())
        if last is None:
            raise RuntimeError("No baseline snapshot exists; retrieve a baseline first.")
        start = (last.acquisition_date + datetime.timedelta(days=1)).date()
        end = datetime.date.today()
        if start > end:
            run.status, run.summary = "No Change", "No time has elapsed since the last snapshot."
        else:
            found = satellite_service.search_imagery(prop.latitude, prop.longitude, start.isoformat(),
                                                     end.isoformat(), settings.MONITORING_MAX_CLOUD_COVER)
            if not found:
                run.status, run.summary = "Inconclusive", "No new cloud-free imagery available yet."
            else:
                best = min(found, key=lambda r: (r["cloud_coverage"], r["acquisition_date"]))
                if db.query(PropertySnapshot).filter(
                        PropertySnapshot.property_id == prop.id,
                        PropertySnapshot.acquisition_date == datetime.datetime.strptime(best["acquisition_date"], "%Y-%m-%d")).first():
                    run.status, run.summary = "No Change", "Latest pass already stored."
                else:
                    hint = ("solar", "pool", "extension")[prop.id % 3] if best["data_origin"] == "DEMO_SYNTHETIC" else "baseline"
                    got = satellite_service.retrieve_imagery(best["catalog_id"], best["acquisition_date"], best["satellite_name"],
                                                             prop.latitude, prop.longitude, hint, best["cloud_coverage"])
                    snap = PropertySnapshot(property_id=prop.id, image_path=got["image_path"], image_source=got["image_source"],
                                            acquisition_date=got["acquisition_date"], cloud_coverage=got["cloud_coverage"],
                                            is_baseline=False, capture_metadata=got["capture_metadata"],
                                            data_origin=got["data_origin"])
                    db.add(snap)
                    db.flush()
                    out["new_snapshot"] = True
                    prop.last_monitoring_date = datetime.datetime.utcnow()
                    cv = run_image_comparison_pipeline(str(snapshot_fs_path(last)), str(snapshot_fs_path(snap)), prop.id)
                    analysis = ImageAnalysis(
                        property_id=prop.id, baseline_snapshot_id=last.id, comparison_snapshot_id=snap.id,
                        algorithm_name=cv["algorithm_name"], change_score=cv["change_score"],
                        changed_area_percentage=cv["changed_area_percentage"], diff_image_path=cv["diff_image_path"],
                        heatmap_image_path=cv["heatmap_image_path"], contours_count=cv["contours_count"],
                        analysis_result=cv["analysis_result"], explanation=cv["explanation"], limitations=cv["limitations"])
                    db.add(analysis)
                    db.flush()
                    run.change_score = cv["change_score"]
                    run.baseline_asset_id = None
                    if cv["change_score"] >= settings.MONITORING_ALERT_CHANGE_SCORE:
                        mod = Modification(
                            modification_alert_id=_next_alert_id(db), property_id=prop.id, analysis_id=analysis.id,
                            suspected_category="Potential Modification (automated monitoring)",
                            description=(f"Automated check: {cv['explanation']} Compared {last.acquisition_date:%Y-%m-%d} "
                                         f"with {snap.acquisition_date:%Y-%m-%d} ({snap.data_origin})."),
                            status="New", change_score=cv["change_score"])
                        db.add(mod)
                        db.flush()
                        _notify(db, prop, mod, cv["change_score"])
                        db.add(AuditLog(entity_type="Modification", entity_id=mod.modification_alert_id,
                                        action="AUTOMATED_ALERT_CREATED",
                                        new_state={"score": cv["change_score"], "snapshot_id": snap.id},
                                        notes="Created by scheduled satellite monitoring"))
                        run.status, run.summary = "Change Detected", f"Alert {mod.modification_alert_id} created."
                        out["alert"] = mod.modification_alert_id
                    else:
                        run.status, run.summary = "No Change", f"Change score {cv['change_score']} below alert threshold."
        out["status"], out["message"] = run.status, run.summary or ""
    except (SatelliteUnavailableError, SatelliteProviderError, RuntimeError) as exc:
        run.status, run.summary = "Failed", str(exc)[:500]
        out["status"], out["message"] = "Failed", str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Monitoring check failed for property %s", prop.id)
        run.status, run.summary = "Failed", f"{exc.__class__.__name__}: {exc}"[:500]
        out["status"], out["message"] = "Failed", run.summary
    db.commit()
    return out


def run_monitoring_cycle(property_ids: List[int] = None) -> Dict[str, Any]:
    """Check all monitoring-enabled properties (or the given ids)."""
    db = SessionLocal()
    results: List[Dict[str, Any]] = []
    try:
        q = db.query(Property).filter(Property.monitoring_enabled == True)  # noqa: E712
        if property_ids:
            q = q.filter(Property.id.in_(property_ids))
        for prop in q.all():
            if prop.is_demo and not settings.DEMO_MODE:
                continue  # demo records are never monitored in live mode
            results.append(check_property(db, prop))
    finally:
        db.close()
    return {"checked": len(results), "new_snapshots": sum(r["new_snapshot"] for r in results),
            "alerts_created": sum(1 for r in results if r["alert"]),
            "failed": sum(1 for r in results if r["status"] == "Failed"), "results": results,
            "finished_at": datetime.datetime.utcnow().isoformat()}


def _scheduled_job():
    if settings.DEMO_MODE and not settings.MONITORING_RUN_IN_DEMO:
        logger.info("Scheduled monitoring skipped (DEMO_MODE; set MONITORING_RUN_IN_DEMO=true to force).")
        return
    summary = run_monitoring_cycle()
    logger.info("Monitoring cycle: %s checked, %s alerts, %s failed",
                summary["checked"], summary["alerts_created"], summary["failed"])


def start_scheduler():
    global _scheduler
    if not settings.MONITORING_ENABLED or _scheduler is not None:
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.error("apscheduler not installed; automated monitoring disabled (pip install apscheduler).")
        return None
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_scheduled_job, "interval", hours=settings.MONITORING_INTERVAL_HOURS,
                       id="satellite-monitoring", max_instances=1, coalesce=True)
    _scheduler.start()
    logger.info("Satellite monitoring scheduled every %s h", settings.MONITORING_INTERVAL_HOURS)
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def scheduler_status() -> Dict[str, Any]:
    job = _scheduler.get_job("satellite-monitoring") if _scheduler else None
    return {"enabled": settings.MONITORING_ENABLED, "running": bool(_scheduler),
            "interval_hours": settings.MONITORING_INTERVAL_HOURS,
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            "skipped_in_demo_mode": settings.DEMO_MODE and not settings.MONITORING_RUN_IN_DEMO,
            "alert_change_score_threshold": settings.MONITORING_ALERT_CHANGE_SCORE}
