import os
import time
import uuid
import smtplib
import ssl
import logging
import threading
from datetime import datetime
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
from typing import Dict, Any, Optional, List, Tuple
from flask import Flask

from app.database import db_session
from app.models.all_models import (
    UserSMTPAccount,
    EmailBatch,
    EmailRecipient,
    EmailBatchStatus,
    EmailRecipientStatus,
    EmailBatchSendingMode,
    SMTPAccountStatus
)
from app.security.credential_vault import decrypt_smtp_credentials
from app.services.smtp_validator import validate_smtp_host_ssrf
from app.services.template_renderer import render_template_string

logger = logging.getLogger(__name__)

# Max bounded retry attempts for temporary network/rate-limiting errors
MAX_RETRIES = 2
DELAY_BETWEEN_EMAILS_SECONDS = 0.5  # Polite rate limiting between individual sends


def _build_mime_message(
    from_address: str,
    from_name: Optional[str],
    to_address: str,
    subject: str,
    html_content: Optional[str],
    text_content: Optional[str],
    custom_message_id: Optional[str] = None
) -> EmailMessage:
    """Constructs a clean RFC-compliant EmailMessage with HTML and plain text parts."""
    msg = EmailMessage()
    msg['Subject'] = subject
    if from_name:
        msg['From'] = f"{from_name} <{from_address}>"
    else:
        msg['From'] = from_address
    
    msg['To'] = to_address
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = custom_message_id or make_msgid(domain=from_address.split('@')[-1])

    if text_content and html_content:
        msg.set_content(text_content)
        msg.add_alternative(html_content, subtype='html')
    elif html_content:
        # Fallback text
        msg.set_content("Please view this email in an HTML-compatible client.")
        msg.add_alternative(html_content, subtype='html')
    else:
        msg.set_content(text_content or "")

    return msg


def _connect_and_login_smtp(account: UserSMTPAccount) -> Tuple[Optional[smtplib.SMTP], Optional[str]]:
    """Opens and authenticates the SMTP connection using decrypted user credentials."""
    is_safe, ssrf_err = validate_smtp_host_ssrf(account.smtp_host, account.smtp_port or 587)
    if not is_safe:
        return None, ssrf_err

    credentials = decrypt_smtp_credentials(account.encrypted_credentials, account.encryption_key_version)
    raw_password = credentials.get("password")
    clean_username = account.smtp_username.strip() if isinstance(account.smtp_username, str) else None
    clean_password = raw_password.strip() if isinstance(raw_password, str) else None

    server = None
    try:
        # Phase 1: Connection & TLS handshake
        if account.use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, timeout=20, context=context)
        else:
            server = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=20)
            server.ehlo()
            if account.use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()

        # Phase 2: Authentication
        if clean_username and clean_password:
            try:
                server.login(clean_username, clean_password)
            except smtplib.SMTPAuthenticationError as auth_err:
                err_text = auth_err.smtp_error.decode('utf-8', errors='ignore') if isinstance(auth_err.smtp_error, bytes) else str(auth_err.smtp_error)
                return None, f"SMTP Authentication failed: {auth_err.smtp_code} {err_text}"
            except smtplib.SMTPServerDisconnected:
                return None, "SMTP Authentication failed: Provider closed connection during login. Verify username and App Password."

        return server, None
    except smtplib.SMTPConnectError:
        return None, f"Could not connect to SMTP server {account.smtp_host}:{account.smtp_port}."
    except smtplib.SMTPServerDisconnected:
        return None, f"SMTP server {account.smtp_host}:{account.smtp_port} disconnected unexpectedly."
    except Exception as e:
        return None, f"SMTP Connection error: {str(e)}"



# Alias for Tuple
from typing import Tuple


def execute_batch_sending_worker(app: Flask, batch_id: int):
    """
    Background worker that iterates through all pending recipients in a batch,
    sends individual emails via the user's connected SMTP account, and updates status idempotently.
    """
    with app.app_context():
        batch = db_session.query(EmailBatch).filter_by(id=batch_id).first()
        if not batch:
            logger.error(f"[Bulk Email Worker] Batch {batch_id} not found.")
            return

        if batch.status in (EmailBatchStatus.COMPLETED.value, EmailBatchStatus.CANCELLED.value):
            logger.info(f"[Bulk Email Worker] Batch {batch_id} already in final status {batch.status}.")
            return

        smtp_account = db_session.query(UserSMTPAccount).filter_by(id=batch.smtp_account_id).first()
        if not smtp_account:
            batch.status = EmailBatchStatus.FAILED.value
            batch.error_message = "Connected SMTP account was not found or was deleted."
            db_session.commit()
            return

        # Mark batch as SENDING
        batch.status = EmailBatchStatus.SENDING.value
        batch.started_at = datetime.utcnow()
        db_session.commit()

        # Connect to SMTP server
        server, conn_err = _connect_and_login_smtp(smtp_account)
        if not server:
            batch.status = EmailBatchStatus.FAILED.value
            batch.error_message = f"Failed to establish SMTP session: {conn_err}"
            # Mark account status
            smtp_account.connection_status = SMTPAccountStatus.FAILED.value
            smtp_account.last_error_message = conn_err
            db_session.commit()
            return

        try:
            # Fetch pending or retryable recipients
            recipients = db_session.query(EmailRecipient).filter(
                EmailRecipient.batch_id == batch_id,
                EmailRecipient.status.in_([EmailRecipientStatus.PENDING.value, EmailRecipientStatus.PROCESSING.value])
            ).order_by(EmailRecipient.id.asc()).all()

            accepted_count = batch.accepted_count or 0
            failed_count = batch.failed_count or 0

            for recipient in recipients:
                # Mark as processing
                recipient.status = EmailRecipientStatus.PROCESSING.value
                recipient.attempt_count = (recipient.attempt_count or 0) + 1
                db_session.commit()

                # Determine subject and body based on sending mode
                rec_data = recipient.recipient_data or {}
                if batch.sending_mode == EmailBatchSendingMode.PERSONALIZED.value:
                    subj, _ = render_template_string(batch.subject, rec_data, is_html=False)
                    b_html, _ = render_template_string(batch.body_html, rec_data, is_html=True) if batch.body_html else (None, [])
                    b_text, _ = render_template_string(batch.body_text, rec_data, is_html=False) if batch.body_text else (None, [])
                else:
                    subj = batch.subject
                    b_html = batch.body_html
                    b_text = batch.body_text

                recipient.rendered_subject = subj
                recipient.rendered_body = b_html or b_text

                # Build message
                msg_id = make_msgid(domain=smtp_account.email_address.split('@')[-1])
                msg = _build_mime_message(
                    from_address=smtp_account.email_address,
                    from_name=smtp_account.sender_name,
                    to_address=recipient.email_address,
                    subject=subj,
                    html_content=b_html,
                    text_content=b_text,
                    custom_message_id=msg_id
                )

                # Attempt send with bounded retry
                send_success = False
                send_error = None

                for attempt in range(MAX_RETRIES):
                    try:
                        # Ensure connection is active
                        if server is None:
                            server, conn_err = _connect_and_login_smtp(smtp_account)
                            if not server:
                                raise RuntimeError(f"Reconnection failed: {conn_err}")

                        server.send_message(msg)
                        send_success = True
                        break
                    except smtplib.SMTPServerDisconnected:
                        logger.warning(f"[Bulk Email Worker] Server disconnected, attempting reconnect (attempt {attempt+1})")
                        server = None
                        time.sleep(1)
                    except smtplib.SMTPException as exc:
                        send_error = f"SMTP error: {str(exc)}"
                        # Check if permanent error
                        if isinstance(exc, smtplib.SMTPRecipientsRefused):
                            break # Permanent refusal, do not retry
                        time.sleep(1)
                    except Exception as exc:
                        send_error = f"Delivery attempt failed: {str(exc)}"
                        time.sleep(1)

                if send_success:
                    recipient.status = EmailRecipientStatus.ACCEPTED.value
                    recipient.accepted_at = datetime.utcnow()
                    recipient.provider_message_id = msg_id
                    recipient.error_message = None
                    accepted_count += 1
                else:
                    recipient.status = EmailRecipientStatus.FAILED.value
                    recipient.error_message = send_error or "Unknown delivery error"
                    failed_count += 1

                recipient.updated_at = datetime.utcnow()
                batch.accepted_count = accepted_count
                batch.failed_count = failed_count
                db_session.commit()

                # Rate limiting delay
                time.sleep(DELAY_BETWEEN_EMAILS_SECONDS)

            # Finalize batch status
            batch.status = EmailBatchStatus.COMPLETED.value
            batch.completed_at = datetime.utcnow()
            db_session.commit()

        except Exception as exc:
            logger.exception(f"[Bulk Email Worker] Critical error sending batch {batch_id}: {exc}")
            batch.status = EmailBatchStatus.FAILED.value
            batch.error_message = f"Batch worker encountered unexpected error: {str(exc)}"
            db_session.commit()
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass


def start_batch_sending_job(app: Flask, batch_id: int) -> bool:
    """Spawns an asynchronous background thread for dispatching an email batch."""
    thread = threading.Thread(
        target=execute_batch_sending_worker,
        args=(app, batch_id),
        daemon=True,
        name=f"BulkEmailWorker-Batch-{batch_id}"
    )
    thread.start()
    return True


def reconcile_abandoned_email_batches():
    """
    Startup recovery and maintenance:
    Finds batches stuck in SENDING or QUEUED state from prior server crashes,
    resumes them or marks them failed safely.
    """
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=30)
    stuck_batches = db_session.query(EmailBatch).filter(
        EmailBatch.status.in_([EmailBatchStatus.SENDING.value, EmailBatchStatus.QUEUED.value]),
        EmailBatch.updated_at < cutoff
    ).all()

    recovered = 0
    for b in stuck_batches:
        b.status = EmailBatchStatus.PAUSED.value
        b.error_message = "Sending was interrupted by application restart/timeout. You may resume or retry pending recipients."
        recovered += 1

    if recovered > 0:
        db_session.commit()
        logger.info(f"[Bulk Email Recovery] Reconciled {recovered} stuck email batch(es).")
    return recovered
