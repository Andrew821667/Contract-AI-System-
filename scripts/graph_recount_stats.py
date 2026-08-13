#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пересчёт nodes_count / edges_count у документов графа.

Зачем. Счётчики обновляет `GraphDocumentRepository.update_stats()` при ингесте
документа. Но фаза relink достраивает cross-document рёбра ПОСЛЕ этого и
статистику не трогает, поэтому счётчики отстают: на 10.08.2026 сумма
edges_count по 8212 документам была 788 963 при 879 854 рёбрах в графе —
недосчёт 90 891 (примерно 10%). Числа видны в админке (Graph-RAG, карточка
документа) и в ответах read-tools, то есть врут пользователю.

Семантика намеренно повторяет update_stats():
  nodes_count — неархивные узлы документа;
  edges_count — рёбра, ИСХОДЯЩИЕ из узлов документа (включая связи на другие
                документы: у ребра ровно один источник, поэтому сумма по всем
                документам должна сходиться с общим числом рёбер).

Один проход агрегации во временной таблице вместо 8212 отдельных запросов:
на проде это секунды против часов.

Запуск:
    python scripts/graph_recount_stats.py --dry-run   # только показать расхождения
    python scripts/graph_recount_stats.py             # применить
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from src.models.database import SessionLocal  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="только показать, ничего не менять")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        before = db.execute(text("""
            SELECT (SELECT COUNT(*) FROM graph_edges),
                   (SELECT COALESCE(SUM(edges_count), 0) FROM graph_documents),
                   (SELECT COUNT(*) FROM graph_nodes WHERE is_archived = 0),
                   (SELECT COALESCE(SUM(nodes_count), 0) FROM graph_documents),
                   (SELECT COUNT(*) FROM graph_documents)
        """)).fetchone()
        edges_total, edges_sum, nodes_total, nodes_sum, docs = before
        print("ДО:")
        print(f"  документов:      {docs}")
        print(f"  рёбер в графе:   {edges_total}  | сумма счётчиков: {edges_sum}  | расхождение: {edges_total - edges_sum}")
        print(f"  узлов в графе:   {nodes_total}  | сумма счётчиков: {nodes_sum}  | расхождение: {nodes_total - nodes_sum}")

        db.execute(text("DROP TABLE IF EXISTS _recount_edges"))
        db.execute(text("DROP TABLE IF EXISTS _recount_nodes"))
        db.execute(text("""
            CREATE TEMP TABLE _recount_edges AS
            SELECT n.document_id AS doc_id, COUNT(*) AS cnt
            FROM graph_edges e
            JOIN graph_nodes n ON n.id = e.source_id
            WHERE n.document_id IS NOT NULL
            GROUP BY n.document_id
        """))
        db.execute(text("""
            CREATE TEMP TABLE _recount_nodes AS
            SELECT document_id AS doc_id, COUNT(*) AS cnt
            FROM graph_nodes
            WHERE is_archived = 0 AND document_id IS NOT NULL
            GROUP BY document_id
        """))

        diff = db.execute(text("""
            SELECT COUNT(*) FROM graph_documents d
            WHERE d.edges_count IS NOT (SELECT COALESCE((SELECT cnt FROM _recount_edges r WHERE r.doc_id = d.id), 0))
               OR d.nodes_count IS NOT (SELECT COALESCE((SELECT cnt FROM _recount_nodes r WHERE r.doc_id = d.id), 0))
        """)).scalar()
        print(f"\nдокументов с расхождением: {diff}")

        if args.dry_run:
            print("\n--dry-run: изменения не применялись")
            return 0

        db.execute(text("""
            UPDATE graph_documents
               SET edges_count = COALESCE((SELECT cnt FROM _recount_edges r WHERE r.doc_id = graph_documents.id), 0),
                   nodes_count = COALESCE((SELECT cnt FROM _recount_nodes r WHERE r.doc_id = graph_documents.id), 0)
        """))
        db.commit()

        after = db.execute(text("""
            SELECT (SELECT COUNT(*) FROM graph_edges),
                   (SELECT COALESCE(SUM(edges_count), 0) FROM graph_documents),
                   (SELECT COUNT(*) FROM graph_nodes WHERE is_archived = 0),
                   (SELECT COALESCE(SUM(nodes_count), 0) FROM graph_documents)
        """)).fetchone()
        print("\nПОСЛЕ:")
        print(f"  рёбер в графе:   {after[0]}  | сумма счётчиков: {after[1]}  | расхождение: {after[0] - after[1]}")
        print(f"  узлов в графе:   {after[2]}  | сумма счётчиков: {after[3]}  | расхождение: {after[2] - after[3]}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
