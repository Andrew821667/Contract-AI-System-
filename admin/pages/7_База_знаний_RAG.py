# -*- coding: utf-8 -*-
"""
RAG Knowledge Base — Управление базой знаний
Загрузка, просмотр и удаление документов для RAG-системы
"""
import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import streamlit as st

# Путь к корню проекта
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from admin.shared.session_helpers import (
    init_session_state, check_admin_auth, show_admin_sidebar_user,
    get_api_keys_status,
)
from admin.shared.ui_components import apply_custom_css, section_header

apply_custom_css()
init_session_state()

if not check_admin_auth():
    st.stop()

# ─── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📚 База знаний RAG")
    st.caption("Загрузка и управление документами")
    st.markdown("---")
    show_admin_sidebar_user()

# ─── Constants ────────────────────────────────────────────────

DOC_TYPES = {
    "law": "Закон / НПА",
    "court_practice": "Судебная практика",
    "template": "Шаблон договора",
    "regulation": "Регламент / Положение",
    "guideline": "Методические рекомендации",
    "article": "Статья / Комментарий",
    "other": "Прочее",
}

RAG_DATA_DIR = project_root / "data" / "rag_documents"
RAG_INDEX_FILE = RAG_DATA_DIR / "_index.json"

# Ensure directories exist
RAG_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ─── Helper functions ─────────────────────────────────────────

def load_rag_index() -> List[Dict]:
    """Load RAG document index from disk."""
    if RAG_INDEX_FILE.exists():
        try:
            return json.loads(RAG_INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_rag_index(index: List[Dict]):
    """Save RAG document index to disk."""
    RAG_INDEX_FILE.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def extract_text_from_file(uploaded_file) -> Optional[str]:
    """Extract text from uploaded file (txt, md, pdf, docx)."""
    name = uploaded_file.name.lower()
    content = uploaded_file.read()

    if name.endswith((".txt", ".md")):
        return content.decode("utf-8", errors="replace")

    if name.endswith(".pdf"):
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return "\n\n".join(text_parts)
        except ImportError:
            st.error("PyMuPDF (fitz) не установлен. Установите: pip install PyMuPDF")
            return None
        except Exception as e:
            st.error(f"Ошибка чтения PDF: {e}")
            return None

    if name.endswith(".docx"):
        try:
            import docx
            import io
            doc = docx.Document(io.BytesIO(content))
            return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except ImportError:
            st.error("python-docx не установлен. Установите: pip install python-docx")
            return None
        except Exception as e:
            st.error(f"Ошибка чтения DOCX: {e}")
            return None

    st.error(f"Неподдерживаемый формат: {name}")
    return None


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
    """Simple text chunking with overlap."""
    chunks = []
    start = 0
    chunk_id = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text_part = text[start:end]
        # Try to break at paragraph or sentence boundary
        if end < len(text):
            last_para = chunk_text_part.rfind("\n\n")
            if last_para > chunk_size * 0.5:
                end = start + last_para + 2
                chunk_text_part = text[start:end]
            else:
                last_period = chunk_text_part.rfind(". ")
                if last_period > chunk_size * 0.5:
                    end = start + last_period + 2
                    chunk_text_part = text[start:end]

        chunks.append({
            "chunk_id": chunk_id,
            "content": chunk_text_part.strip(),
            "start": start,
            "end": end,
        })
        chunk_id += 1
        start = end - overlap
        if start < 0:
            start = 0
        # Safety: avoid infinite loop
        if end >= len(text):
            break

    return chunks


def index_document_to_chroma(
    doc_id: str,
    title: str,
    doc_type: str,
    text: str,
    tags: List[str],
) -> int:
    """Index document chunks into ChromaDB. Returns number of chunks indexed."""
    try:
        from src.services.enhanced_rag import EnhancedRAGSystem, CHROMA_AVAILABLE
        if not CHROMA_AVAILABLE:
            st.warning("ChromaDB не доступен. Документ сохранён только на диск.")
            return 0

        rag = get_rag_system()
        if rag is None:
            return 0

        # Use add_company_knowledge which handles chunking + vectorization
        rag.add_company_knowledge(
            title=title,
            content=text,
            category=doc_type,
            tags=tags,
            author=st.session_state.get("admin_user_email", "admin"),
        )

        # Count chunks for reporting
        chunks = chunk_text(text)
        return len(chunks)

    except Exception as e:
        st.warning(f"Индексация в ChromaDB не удалась: {e}. Документ сохранён на диск.")
        return 0


@st.cache_resource
def get_rag_system():
    """Get or create RAG system instance (cached)."""
    try:
        from src.services.enhanced_rag import EnhancedRAGSystem
        return EnhancedRAGSystem(
            persist_directory=str(project_root / "data" / "chroma_enhanced")
        )
    except Exception as e:
        st.warning(f"RAG система недоступна: {e}")
        return None


def delete_document(doc_id: str, index: List[Dict]) -> List[Dict]:
    """Delete document from index and disk."""
    # Remove from index
    new_index = [d for d in index if d.get("id") != doc_id]

    # Remove file from disk
    for ext in [".md", ".txt"]:
        fpath = RAG_DATA_DIR / f"{doc_id}{ext}"
        if fpath.exists():
            fpath.unlink()

    # Try to remove from ChromaDB
    try:
        rag = get_rag_system()
        if rag and rag.kb_collection:
            # Delete all chunks with this doc_id
            results = rag.kb_collection.get(where={"kb_id": doc_id})
            if results and results["ids"]:
                rag.kb_collection.delete(ids=results["ids"])
    except Exception:
        pass  # Non-critical

    save_rag_index(new_index)
    return new_index


# ─── Main Content ─────────────────────────────────────────────

section_header(
    "📚 База знаний RAG",
    "Загрузка и управление документами для AI-анализа договоров"
)

tab_upload, tab_browse, tab_stats = st.tabs(["📤 Загрузка", "📋 Документы", "📊 Статистика"])

# ═══════════════════════════════════════════════════════════════
# TAB 1: Upload
# ═══════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown("### Загрузка документа в базу знаний")
    st.info(
        "Загрузите закон, судебную практику, шаблон или методические рекомендации. "
        "Документ будет разбит на чанки, векторизован и добавлен в RAG для использования при анализе договоров."
    )

    with st.form("upload_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            doc_title = st.text_input(
                "Название документа *",
                placeholder="Например: ГК РФ Глава 30 — Купля-продажа"
            )
            doc_type = st.selectbox(
                "Тип документа *",
                options=list(DOC_TYPES.keys()),
                format_func=lambda x: DOC_TYPES[x],
            )

        with col2:
            doc_tags = st.text_input(
                "Теги (через запятую)",
                placeholder="гк рф, купля-продажа, обязательства"
            )
            doc_description = st.text_area(
                "Описание (необязательно)",
                placeholder="Краткое описание содержания документа",
                height=68,
            )

        uploaded_file = st.file_uploader(
            "Файл документа *",
            type=["txt", "md", "pdf", "docx"],
            help="Поддерживаемые форматы: TXT, MD, PDF, DOCX"
        )

        # Manual text input as alternative
        manual_text = st.text_area(
            "Или вставьте текст вручную",
            placeholder="Вставьте текст документа здесь, если не хотите загружать файл...",
            height=150,
        )

        submitted = st.form_submit_button(
            "📤 Загрузить в базу знаний",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        if not doc_title:
            st.error("Укажите название документа")
        elif not uploaded_file and not manual_text.strip():
            st.error("Загрузите файл или вставьте текст")
        else:
            with st.spinner("Обработка документа..."):
                # Extract text
                if uploaded_file:
                    text = extract_text_from_file(uploaded_file)
                    source_file = uploaded_file.name
                else:
                    text = manual_text.strip()
                    source_file = "manual_input"

                if text and len(text) > 10:
                    # Generate unique ID
                    doc_id = hashlib.sha256(
                        f"{doc_title}_{datetime.now().isoformat()}".encode()
                    ).hexdigest()[:16]

                    # Parse tags
                    tags = [t.strip() for t in doc_tags.split(",") if t.strip()] if doc_tags else []

                    # Save text as markdown to disk
                    md_content = f"# {doc_title}\n\n"
                    if doc_description:
                        md_content += f"> {doc_description}\n\n"
                    md_content += f"**Тип:** {DOC_TYPES.get(doc_type, doc_type)}  \n"
                    md_content += f"**Теги:** {', '.join(tags)}  \n"
                    md_content += f"**Дата загрузки:** {datetime.now().strftime('%d.%m.%Y %H:%M')}  \n\n"
                    md_content += "---\n\n"
                    md_content += text

                    doc_file = RAG_DATA_DIR / f"{doc_id}.md"
                    doc_file.write_text(md_content, encoding="utf-8")

                    # Chunk info
                    chunks = chunk_text(text)

                    # Index in ChromaDB
                    indexed_chunks = index_document_to_chroma(
                        doc_id=doc_id,
                        title=doc_title,
                        doc_type=doc_type,
                        text=text,
                        tags=tags,
                    )

                    # Add to index
                    index = load_rag_index()
                    index.append({
                        "id": doc_id,
                        "title": doc_title,
                        "type": doc_type,
                        "description": doc_description or "",
                        "tags": tags,
                        "source_file": source_file,
                        "char_count": len(text),
                        "chunk_count": len(chunks),
                        "indexed_chunks": indexed_chunks,
                        "uploaded_by": st.session_state.get("admin_user_email", "admin"),
                        "uploaded_at": datetime.now().isoformat(),
                    })
                    save_rag_index(index)

                    st.success(
                        f"Документ загружен: **{doc_title}**\n\n"
                        f"- {len(text):,} символов\n"
                        f"- {len(chunks)} чанков\n"
                        f"- {'Проиндексирован в ChromaDB' if indexed_chunks > 0 else 'Сохранён на диск (ChromaDB недоступен)'}"
                    )
                else:
                    st.error("Не удалось извлечь текст из документа или текст слишком короткий")

# ═══════════════════════════════════════════════════════════════
# TAB 2: Browse documents
# ═══════════════════════════════════════════════════════════════
with tab_browse:
    st.markdown("### Документы в базе знаний")

    index = load_rag_index()

    if not index:
        st.info("База знаний пуста. Загрузите документы на вкладке «Загрузка».")
    else:
        # Filter
        filter_type = st.selectbox(
            "Фильтр по типу",
            options=["all"] + list(DOC_TYPES.keys()),
            format_func=lambda x: "Все типы" if x == "all" else DOC_TYPES.get(x, x),
        )

        filtered = index if filter_type == "all" else [d for d in index if d.get("type") == filter_type]

        st.caption(f"Показано {len(filtered)} из {len(index)} документов")

        for doc in sorted(filtered, key=lambda d: d.get("uploaded_at", ""), reverse=True):
            with st.expander(
                f"{'📜' if doc.get('type') == 'law' else '⚖️' if doc.get('type') == 'court_practice' else '📄'} "
                f"**{doc.get('title', 'Без названия')}** — "
                f"{DOC_TYPES.get(doc.get('type', ''), doc.get('type', ''))} | "
                f"{doc.get('char_count', 0):,} симв. | {doc.get('chunk_count', 0)} чанков"
            ):
                col1, col2 = st.columns([3, 1])

                with col1:
                    if doc.get("description"):
                        st.markdown(f"*{doc['description']}*")

                    tags = doc.get("tags", [])
                    if tags:
                        st.markdown("**Теги:** " + ", ".join(f"`{t}`" for t in tags))

                    st.caption(
                        f"ID: {doc.get('id', '?')} | "
                        f"Источник: {doc.get('source_file', '?')} | "
                        f"Загружен: {doc.get('uploaded_at', '?')[:16]} | "
                        f"Кем: {doc.get('uploaded_by', '?')}"
                    )

                    # Show preview
                    doc_file = RAG_DATA_DIR / f"{doc.get('id', '')}.md"
                    if doc_file.exists():
                        preview = doc_file.read_text(encoding="utf-8")
                        # Show first 500 chars of actual content (skip header)
                        content_start = preview.find("---\n\n")
                        if content_start > 0:
                            content_preview = preview[content_start + 5:content_start + 505]
                        else:
                            content_preview = preview[:500]
                        st.text_area(
                            "Превью содержимого",
                            value=content_preview + ("..." if len(preview) > 500 else ""),
                            height=120,
                            disabled=True,
                            key=f"preview_{doc.get('id')}",
                        )

                with col2:
                    indexed = doc.get("indexed_chunks", 0)
                    if indexed > 0:
                        st.success(f"ChromaDB: {indexed} чанков")
                    else:
                        st.warning("Не в ChromaDB")

                    if st.button(
                        "🗑 Удалить",
                        key=f"del_{doc.get('id')}",
                        type="secondary",
                        use_container_width=True,
                    ):
                        st.session_state[f"confirm_delete_{doc.get('id')}"] = True

                    if st.session_state.get(f"confirm_delete_{doc.get('id')}"):
                        st.warning("Точно удалить?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("Да", key=f"yes_{doc.get('id')}", use_container_width=True):
                                index = delete_document(doc["id"], index)
                                st.session_state.pop(f"confirm_delete_{doc['id']}", None)
                                st.success("Удалён")
                                st.rerun()
                        with col_no:
                            if st.button("Нет", key=f"no_{doc.get('id')}", use_container_width=True):
                                st.session_state.pop(f"confirm_delete_{doc['id']}", None)
                                st.rerun()

# ═══════════════════════════════════════════════════════════════
# TAB 3: Stats
# ═══════════════════════════════════════════════════════════════
with tab_stats:
    st.markdown("### Статистика базы знаний")

    index = load_rag_index()

    if not index:
        st.info("Нет документов для статистики.")
    else:
        # Summary metrics
        total_docs = len(index)
        total_chars = sum(d.get("char_count", 0) for d in index)
        total_chunks = sum(d.get("chunk_count", 0) for d in index)
        indexed_docs = sum(1 for d in index if d.get("indexed_chunks", 0) > 0)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Документов", total_docs)
        with col2:
            st.metric("Символов", f"{total_chars:,}")
        with col3:
            st.metric("Чанков", total_chunks)
        with col4:
            st.metric("В ChromaDB", indexed_docs)

        st.markdown("---")

        # By type
        st.markdown("#### По типу документа")
        type_counts = {}
        for d in index:
            t = d.get("type", "other")
            type_counts[t] = type_counts.get(t, 0) + 1

        for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            label = DOC_TYPES.get(t, t)
            st.progress(count / total_docs, text=f"{label}: {count}")

        # ChromaDB status
        st.markdown("---")
        st.markdown("#### Статус ChromaDB")
        try:
            rag = get_rag_system()
            if rag and rag.kb_collection:
                kb_count = rag.kb_collection.count()
                st.success(f"company_kb: {kb_count} чанков")

                if rag.contracts_collection:
                    contracts_count = rag.contracts_collection.count()
                    st.info(f"contracts: {contracts_count} чанков")

                if rag.legal_collection:
                    legal_count = rag.legal_collection.count()
                    st.info(f"legal_docs: {legal_count} чанков")
            else:
                st.warning("ChromaDB недоступен")
        except Exception as e:
            st.warning(f"Не удалось получить статистику ChromaDB: {e}")
