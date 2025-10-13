# -*- coding: utf-8 -*-
"""
Disagreement Export Service - Export disagreements to various formats
Supports: DOCX, PDF, Email, EDO
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import hashlib
from loguru import logger

from ..models.disagreement_models import Disagreement, DisagreementObjection, DisagreementExportLog


class DisagreementExportService:
    """
    Service for exporting disagreements
    
    Formats:
    - DOCX: Official document with letterhead
    - PDF: Generated from DOCX
    - Email: SMTP with template
    - EDO: Electronic document management (stubs)
    """

    def __init__(self, db_session, config: Optional[Dict[str, Any]] = None):
        self.db_session = db_session
        self.config = config or {}
        
        # Export paths
        self.export_dir = self.config.get('export_dir', 'data/exports/disagreements')
        os.makedirs(self.export_dir, exist_ok=True)
        
        # SMTP settings (from config)
        self.smtp_host = self.config.get('smtp_host', 'smtp.gmail.com')
        self.smtp_port = self.config.get('smtp_port', 587)
        self.smtp_user = self.config.get('smtp_user')
        self.smtp_password = self.config.get('smtp_password')
        
        # EDO settings (stubs)
        self.edo_endpoints = self.config.get('edo_endpoints', {
            'diadoc': 'https://api.diadoc.ru',
            'sbis': 'https://api.sbis.ru',
            'kontur': 'https://api.kontur.ru/edo'
        })

    def export_to_docx(
        self, disagreement_id: int, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export disagreement to DOCX format with official letterhead
        
        Args:
            disagreement_id: ID of disagreement
            user_id: ID of user performing export
            
        Returns:
            Dict with file_path and metadata
        """
        try:
            logger.info(f"Exporting disagreement {disagreement_id} to DOCX")

            disagreement = self.db_session.query(Disagreement).filter(
                Disagreement.id == disagreement_id
            ).first()

            if not disagreement:
                raise ValueError(f"Disagreement {disagreement_id} not found")

            # Get selected objections
            selected_ids = disagreement.priority_order or disagreement.selected_objections
            objections = self.db_session.query(DisagreementObjection).filter(
                DisagreementObjection.id.in_(selected_ids)
            ).all()

            # Sort by priority order
            objections_dict = {obj.id: obj for obj in objections}
            sorted_objections = [objections_dict[oid] for oid in selected_ids if oid in objections_dict]

            # Generate DOCX content (stub - real implementation would use python-docx)
            file_path = os.path.join(
                self.export_dir,
                f"disagreement_{disagreement_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            )

            # Stub: in production would use python-docx library
            docx_content = self._generate_docx_content_stub(disagreement, sorted_objections)
            
            # Save stub file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(docx_content)

            file_size = os.path.getsize(file_path)
            file_hash = self._calculate_file_hash(file_path)

            # Update disagreement
            disagreement.docx_path = file_path
            self.db_session.commit()

            # Log export
            self._log_export(
                disagreement_id, 'docx', file_path, file_size, file_hash, user_id
            )

            logger.info(f"DOCX exported: {file_path}")

            return {
                'success': True,
                'file_path': file_path,
                'file_size': file_size,
                'file_hash': file_hash
            }

        except Exception as e:
            logger.error(f"DOCX export failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _generate_docx_content_stub(
        self, disagreement: Disagreement, objections: List[DisagreementObjection]
    ) -> str:
        """
        Generate DOCX content (stub version - text format)
        
        Real implementation would use python-docx:
        - Official letterhead with logo
        - Proper formatting (headers, numbering, tables)
        - References to contract clauses
        """
        content = []
        
        # Header
        content.append("ВОЗРАЖЕНИЯ К ПРОЕКТУ ДОГОВОРА")
        content.append("=" * 60)
        content.append(f"Дата: {datetime.now().strftime('%d.%m.%Y')}")
        content.append(f"ID договора: {disagreement.contract_id}")
        content.append("")
        
        # Objections
        content.append("ЗАМЕЧАНИЯ И ПРЕДЛОЖЕНИЯ:")
        content.append("")
        
        for i, obj in enumerate(objections, 1):
            content.append(f"{i}. Пункт договора: {obj.contract_section_xpath or 'не указан'}")
            content.append(f"   Приоритет: {obj.priority.upper()}")
            content.append("")
            content.append(f"   Замечание:")
            content.append(f"   {obj.issue_description}")
            content.append("")
            
            if obj.legal_basis:
                content.append(f"   Правовое обоснование:")
                content.append(f"   {obj.legal_basis}")
                content.append("")
            
            if obj.risk_explanation:
                content.append(f"   Риски:")
                content.append(f"   {obj.risk_explanation}")
                content.append("")
            
            content.append(f"   Предлагаемая формулировка:")
            content.append(f"   {obj.alternative_formulation}")
            content.append("")
            
            if obj.alternative_reasoning:
                content.append(f"   Обоснование предложения:")
                content.append(f"   {obj.alternative_reasoning}")
                content.append("")
            
            content.append("-" * 60)
            content.append("")
        
        # Footer
        content.append("")
        content.append(f"Всего замечаний: {len(objections)}")
        content.append("")
        content.append("С уважением,")
        content.append("[Подпись]")
        content.append("[Должность]")
        
        return "\n".join(content)

    def export_to_pdf(
        self, disagreement_id: int, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export disagreement to PDF
        
        Real implementation would convert DOCX to PDF using:
        - LibreOffice headless
        - docx2pdf
        - reportlab
        """
        try:
            logger.info(f"Exporting disagreement {disagreement_id} to PDF")

            # First ensure DOCX exists
            disagreement = self.db_session.query(Disagreement).filter(
                Disagreement.id == disagreement_id
            ).first()

            if not disagreement.docx_path or not os.path.exists(disagreement.docx_path):
                # Generate DOCX first
                docx_result = self.export_to_docx(disagreement_id, user_id)
                if not docx_result['success']:
                    return docx_result

            # Stub: would convert DOCX to PDF
            pdf_path = disagreement.docx_path.replace('.docx', '.pdf')
            
            # Stub conversion
            with open(disagreement.docx_path, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(pdf_path, 'w', encoding='utf-8') as f:
                f.write(f"PDF VERSION:\n{content}")

            file_size = os.path.getsize(pdf_path)
            file_hash = self._calculate_file_hash(pdf_path)

            # Update disagreement
            disagreement.pdf_path = pdf_path
            self.db_session.commit()

            # Log export
            self._log_export(
                disagreement_id, 'pdf', pdf_path, file_size, file_hash, user_id
            )

            logger.info(f"PDF exported: {pdf_path}")

            return {
                'success': True,
                'file_path': pdf_path,
                'file_size': file_size,
                'file_hash': file_hash
            }

        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_via_email(
        self,
        disagreement_id: int,
        recipient_email: str,
        subject: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send disagreement via email
        
        Args:
            disagreement_id: ID of disagreement
            recipient_email: Recipient email address
            subject: Email subject (optional)
            user_id: ID of user sending email
        """
        try:
            logger.info(f"Sending disagreement {disagreement_id} via email to {recipient_email}")

            disagreement = self.db_session.query(Disagreement).filter(
                Disagreement.id == disagreement_id
            ).first()

            if not disagreement:
                raise ValueError(f"Disagreement {disagreement_id} not found")

            # Ensure PDF exists
            if not disagreement.pdf_path or not os.path.exists(disagreement.pdf_path):
                pdf_result = self.export_to_pdf(disagreement_id, user_id)
                if not pdf_result['success']:
                    return pdf_result

            # Email subject
            if not subject:
                subject = f"Возражения к проекту договора № {disagreement.contract_id}"

            # Stub: Real implementation would use smtplib
            email_sent = self._send_email_stub(
                recipient_email, subject, disagreement.pdf_path
            )

            # Log export
            export_log = self._log_export(
                disagreement_id, 'email', disagreement.pdf_path, 
                os.path.getsize(disagreement.pdf_path),
                self._calculate_file_hash(disagreement.pdf_path),
                user_id
            )

            export_log.email_to = recipient_email
            export_log.email_subject = subject
            export_log.email_sent_at = datetime.utcnow()
            export_log.email_status = 'sent' if email_sent else 'failed'
            self.db_session.commit()

            logger.info(f"Email sent to {recipient_email}")

            return {
                'success': email_sent,
                'recipient': recipient_email,
                'subject': subject,
                'attachment': disagreement.pdf_path
            }

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _send_email_stub(self, recipient: str, subject: str, attachment_path: str) -> bool:
        """
        Stub for email sending
        
        Real implementation would use:
        ```python
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        
        msg = MIMEMultipart()
        msg['From'] = self.smtp_user
        msg['To'] = recipient
        msg['Subject'] = subject
        
        # Attach file
        with open(attachment_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
        msg.attach(part)
        
        # Send
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.starttls()
        server.login(self.smtp_user, self.smtp_password)
        server.send_message(msg)
        server.quit()
        ```
        """
        logger.info(f"[STUB] Email would be sent to {recipient}")
        logger.info(f"[STUB] Subject: {subject}")
        logger.info(f"[STUB] Attachment: {attachment_path}")
        logger.info(f"[STUB] SMTP: {self.smtp_host}:{self.smtp_port}")
        return True  # Stub always succeeds

    def export_to_edo(
        self,
        disagreement_id: int,
        edo_system: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export to EDO system (Electronic Document Management)
        
        Args:
            disagreement_id: ID of disagreement
            edo_system: 'diadoc', 'sbis', 'kontur', etc.
            user_id: ID of user performing export
        """
        try:
            logger.info(f"Exporting disagreement {disagreement_id} to EDO: {edo_system}")

            disagreement = self.db_session.query(Disagreement).filter(
                Disagreement.id == disagreement_id
            ).first()

            if not disagreement:
                raise ValueError(f"Disagreement {disagreement_id} not found")

            # Ensure PDF exists
            if not disagreement.pdf_path:
                pdf_result = self.export_to_pdf(disagreement_id, user_id)
                if not pdf_result['success']:
                    return pdf_result

            # Get EDO endpoint
            edo_endpoint = self.edo_endpoints.get(edo_system.lower())
            if not edo_endpoint:
                raise ValueError(f"Unknown EDO system: {edo_system}")

            # Stub: Real implementation would call EDO API
            edo_document_id = self._send_to_edo_stub(
                edo_system, edo_endpoint, disagreement.pdf_path
            )

            # Log export
            export_log = self._log_export(
                disagreement_id, 'edo', disagreement.pdf_path,
                os.path.getsize(disagreement.pdf_path),
                self._calculate_file_hash(disagreement.pdf_path),
                user_id
            )

            export_log.edo_system = edo_system
            export_log.edo_document_id = edo_document_id
            export_log.edo_status = 'sent'
            self.db_session.commit()

            logger.info(f"Exported to {edo_system}: {edo_document_id}")

            return {
                'success': True,
                'edo_system': edo_system,
                'edo_document_id': edo_document_id,
                'edo_endpoint': edo_endpoint
            }

        except Exception as e:
            logger.error(f"EDO export failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _send_to_edo_stub(self, edo_system: str, endpoint: str, file_path: str) -> str:
        """
        Stub for EDO API integration
        
        Real implementation would:
        - Authenticate with EDO system
        - Upload document
        - Create document metadata
        - Get document ID
        """
        logger.info(f"[STUB] Would send to {edo_system} at {endpoint}")
        logger.info(f"[STUB] File: {file_path}")
        
        # Generate fake document ID
        doc_id = f"{edo_system.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"[STUB] Generated document ID: {doc_id}")
        
        return doc_id

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _log_export(
        self,
        disagreement_id: int,
        export_type: str,
        file_path: str,
        file_size: int,
        file_hash: str,
        user_id: Optional[str]
    ) -> DisagreementExportLog:
        """Log export to database"""
        export_log = DisagreementExportLog(
            disagreement_id=disagreement_id,
            export_type=export_type,
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            exported_by=user_id
        )
        self.db_session.add(export_log)
        self.db_session.commit()
        self.db_session.refresh(export_log)
        return export_log


__all__ = ["DisagreementExportService"]
