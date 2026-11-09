"""邮件推送工具：基于 smtplib 的简单 SMTP 发送。

用于打卡提醒、会员到期通知等。配置见 app.config.Settings 的 SMTP_*。
未配置或发送失败时，邮件写入 email_outbox 待重试（status='pending'）。
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr

from app.config import settings

logger = logging.getLogger("fitness.email")
BRAND = "康衡康复中心"


def is_configured() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_PASSWORD)


def _base_url() -> str:
    return (settings.PUBLIC_BASE_URL or f"http://localhost:{settings.PORT}").rstrip("/")


def _enqueue_outbox(to: str, subject: str, html: str, reason: str) -> None:
    """邮件未能即时发出时落 outbox，供后续重试。"""
    try:
        from app.database import db
        db.execute(
            "INSERT INTO email_outbox (to_addr, subject, html, status, attempts, last_error) "
            "VALUES (%s, %s, %s, 'pending', 1, %s)",
            (to[:120], subject[:200], html, reason[:500]))
    except Exception as exc:  # outbox 不可用时不影响主流程
        logger.warning("邮件入 outbox 失败: %s", exc)


def send_email(to: str, subject: str, html: str) -> bool:
    """发送一封 HTML 邮件。成功返回 True；未配置或失败返回 False 并落 outbox。"""
    if not is_configured():
        _enqueue_outbox(to, subject, html, "SMTP 未配置")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr((str(Header(BRAND, "utf-8")), settings.SMTP_FROM or settings.SMTP_USER))
        msg["To"] = to
        msg["Subject"] = Header(subject, "utf-8")
        msg.attach(MIMEText(html, "html", "utf-8"))

        if settings.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, [to], msg.as_string())
        server.quit()
        return True
    except Exception as exc:
        _enqueue_outbox(to, subject, html, str(exc))
        return False


def retry_outbox(limit: int = 20) -> dict:
    """重试 outbox 中待发送邮件，返回成功/失败数量。"""
    from app.database import db
    rows = db.query(
        "SELECT * FROM email_outbox WHERE status='pending' ORDER BY id ASC LIMIT %s", (limit,))
    sent = failed = 0
    for row in rows:
        if not is_configured():
            break
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = formataddr((str(Header(BRAND, "utf-8")), settings.SMTP_FROM or settings.SMTP_USER))
            msg["To"] = row["to_addr"]
            msg["Subject"] = Header(row["subject"], "utf-8")
            msg.attach(MIMEText(row["html"] or "", "html", "utf-8"))
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) \
                if settings.SMTP_USE_SSL else smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, [row["to_addr"]], msg.as_string())
            server.quit()
            db.execute("UPDATE email_outbox SET status='sent', sent_at=NOW(), attempts=attempts+1 WHERE id=%s",
                       (row["id"],))
            sent += 1
        except Exception as exc:
            db.execute("UPDATE email_outbox SET attempts=attempts+1, last_error=%s WHERE id=%s",
                       (str(exc)[:500], row["id"]))
            failed += 1
    return {"sent": sent, "failed": failed}


def checkin_reminder_html(nickname: str, streak: int) -> str:
    return f"""
    <div style="font-family:-apple-system,'PingFang SC',sans-serif;max-width:480px;margin:0 auto;padding:24px;background:#16162B;border-radius:14px;color:#E8ECF1">
      <div style="text-align:center;font-size:28px;margin-bottom:12px">🏋️</div>
      <h2 style="color:#FF6B00;text-align:center;margin:0 0 8px">今天还没打卡哦，{nickname}！</h2>
      <p style="text-align:center;color:#B2BEC3;margin:0 0 20px">你已经连续打卡 <b style="color:#FFD93D">{streak}</b> 天，别让努力白费～</p>
      <div style="text-align:center">
        <a href="{_base_url()}/#/checkin" style="display:inline-block;padding:12px 28px;background:#FF6B00;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">立即打卡</a>
      </div>
      <p style="text-align:center;color:#6B7280;font-size:12px;margin-top:24px">{BRAND} · 科学康复 · 循序渐进</p>
    </div>
    """
