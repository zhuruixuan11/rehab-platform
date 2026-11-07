"""邮件推送工具：基于 smtplib 的简单 SMTP 发送。

用于打卡提醒、会员到期通知等。配置见 app.config.Settings 的 SMTP_*。
若 SMTP_USER 为空则视为未配置，send_email 直接返回 False（不抛异常）。
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr

from app.config import settings


def is_configured() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to: str, subject: str, html: str) -> bool:
    """发送一封 HTML 邮件。成功返回 True，未配置或失败返回 False。"""
    if not is_configured():
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr((str(Header("健持健身", "utf-8")), settings.SMTP_FROM or settings.SMTP_USER))
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
    except Exception:
        return False


def checkin_reminder_html(nickname: str, streak: int) -> str:
    return f"""
    <div style="font-family:-apple-system,'PingFang SC',sans-serif;max-width:480px;margin:0 auto;padding:24px;background:#16162B;border-radius:14px;color:#E8ECF1">
      <div style="text-align:center;font-size:28px;margin-bottom:12px">🏋️</div>
      <h2 style="color:#FF6B00;text-align:center;margin:0 0 8px">今天还没打卡哦，{nickname}！</h2>
      <p style="text-align:center;color:#B2BEC3;margin:0 0 20px">你已经连续打卡 <b style="color:#FFD93D">{streak}</b> 天，别让努力白费～</p>
      <div style="text-align:center">
        <a href="http://localhost:8002/#/checkin" style="display:inline-block;padding:12px 28px;background:#FF6B00;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">立即打卡</a>
      </div>
      <p style="text-align:center;color:#6B7280;font-size:12px;margin-top:24px">健持 · 科学训练 · 持之以恒</p>
    </div>
    """
