"""LLM Wiki - Structured knowledge page organization

Beyond simple RAG, LLM Wiki organizes parsed documents into:
- Document cards: metadata + summary
- Chapter summaries: per-section understanding
- Concept pages: key terms extracted from documents
- Table descriptions: structured table explanations
- Image descriptions: figure/photo explanations
- Cross-document index: links between related documents
"""

import os
import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import defaultdict


class WikiPage:
    """A structured knowledge page"""
    def __init__(self, page_id: str, title: str, page_type: str, content: str,
                 document_id: str = "", metadata: Dict = None):
        self.id = page_id
        self.title = title
        self.page_type = page_type  # document_card, chapter_summary, concept, table_desc, image_desc
        self.content = content
        self.document_id = document_id
        self.metadata = metadata or {}
        self.links: List[str] = []  # Links to other wiki pages
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at


class LLMWiki:
    """LLM Wiki - structured knowledge organization system"""

    def __init__(self, persist_dir: str = "./wiki_db"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self.pages: Dict[str, WikiPage] = {}
        self.doc_index: Dict[str, List[str]] = defaultdict(list)  # document_id -> page_ids
        self.type_index: Dict[str, List[str]] = defaultdict(list)  # page_type -> page_ids
        self._load()

    def build_from_document(self, parsed_doc) -> List[WikiPage]:
        """Build wiki pages from a parsed document"""
        doc_id = parsed_doc.id
        filename = parsed_doc.filename
        created_pages = []

        # 1. Document card
        card = WikiPage(
            page_id=f"doc_card_{doc_id}",
            title=filename,
            page_type="document_card",
            content=self._build_document_card(parsed_doc),
            document_id=doc_id,
            metadata={
                "filename": filename,
                "file_type": parsed_doc.file_type,
                "pages": parsed_doc.metadata.get("page_count", 0),
                "parse_time": parsed_doc.metadata.get("parse_time", ""),
                "errors": len(parsed_doc.parse_errors)
            }
        )
        self.add_page(card)
        created_pages.append(card)

        # 2. Chapter summaries (from pages)
        for page_data in parsed_doc.pages:
            page_num = page_data.get("page_num", 1)
            text = page_data.get("text", "")
            if text.strip():
                # Generate chapter summary
                summary = text[:500] + "..." if len(text) > 500 else text
                chapter = WikiPage(
                    page_id=f"chapter_{doc_id}_p{page_num}",
                    title=f"Page {page_num} - {filename}",
                    page_type="chapter_summary",
                    content=summary,
                    document_id=doc_id,
                    metadata={"page_number": page_num, "text_length": len(text)}
                )
                self.add_page(chapter)
                created_pages.append(chapter)

        # 3. Table descriptions
        for i, table_data in enumerate(parsed_doc.tables):
            md = table_data.get("markdown", "")
            source = table_data.get("source", "")
            if md:
                table_desc = WikiPage(
                    page_id=f"table_{doc_id}_{i}",
                    title=f"Table {i + 1} - {filename}",
                    page_type="table_desc",
                    content=f"Source: {source}\n\n{md}\n\n"
                            f"Rows: {table_data.get('rows', 0)}, "
                            f"Cols: {table_data.get('cols', 0)}",
                    document_id=doc_id,
                    metadata={
                        "table_index": i,
                        "source": source,
                        "rows": table_data.get("rows", 0),
                        "cols": table_data.get("cols", 0)
                    }
                )
                self.add_page(table_desc)
                created_pages.append(table_desc)

        # 4. Key concepts extraction
        concepts = self._extract_concepts(parsed_doc)
        for concept_name, concept_desc in concepts.items():
            concept_page = WikiPage(
                page_id=f"concept_{doc_id}_{concept_name.lower().replace(' ', '_')}",
                title=concept_name,
                page_type="concept",
                content=f"**{concept_name}**: {concept_desc}\n\n"
                        f"(Extracted from: {filename})",
                document_id=doc_id,
                metadata={"concept": concept_name}
            )
            self.add_page(concept_page)
            created_pages.append(concept_page)

        self._save()
        return created_pages

    def _build_document_card(self, parsed_doc) -> str:
        """Generate a document card summary"""
        parts = [
            f"# Document: {parsed_doc.filename}",
            f"- **Type**: {parsed_doc.file_type}",
            f"- **Pages/Slides**: {parsed_doc.metadata.get('page_count', 'N/A')}",
            f"- **Parse Time**: {parsed_doc.metadata.get('parse_time', 'N/A')}",
            f"- **Parse Errors**: {len(parsed_doc.parse_errors)}",
            f"- **Tables Found**: {len(parsed_doc.tables)}",
            "",
            "## Content Preview",
        ]

        for page in parsed_doc.pages[:3]:
            text = page.get("text", "")
            parts.append(f"\n--- Page {page.get('page_num', 1)} ---")
            parts.append(text[:300] if text else "(No text)")

        if parsed_doc.tables:
            parts.append(f"\n## Tables ({len(parsed_doc.tables)})")
            for i, t in enumerate(parsed_doc.tables[:3]):
                parts.append(f"- Table {i + 1}: {t.get('rows', 0)}x{t.get('cols', 0)} "
                             f"(source: {t.get('source', 'unknown')})")

        return "\n".join(parts)

    def _extract_concepts(self, parsed_doc) -> Dict[str, str]:
        """Extract key concepts from document text using simple NLP"""
        concepts = {}
        text = "\n".join(p.get("text", "") for p in parsed_doc.pages if p.get("text"))

        # Extract capitalized terms (potential named entities)
        capitalized_terms = re.findall(r'\b([A-Z一-鿿][A-Za-z一-鿿]{1,20})\b', text)

        # Count frequencies (simple)
        from collections import Counter
        term_counts = Counter()
        for term in capitalized_terms:
            if len(term) >= 2:
                term_counts[term] += 1

        # Filter to meaningful terms
        stopwords = {'The', 'This', 'That', 'These', 'Those', 'We', 'Our', 'It', 'Its',
                     'They', 'He', 'She', 'For', 'With', 'From', 'Are', 'Has', 'Have',
                     'Fig', 'Table', 'Figure', 'Eq', 'Equation', 'Section', 'Chapter',
                     'Appendix', 'Introduction', 'Method', 'Result', 'Conclusion',
                     'Data', 'Model', 'Analysis', 'Example', 'Step', 'Note', 'Notes'}
        for term, count in term_counts.most_common(20):
            if term not in stopwords and count >= 2:
                # Find context
                context_pattern = re.search(
                    rf'.{{0,100}}{re.escape(term)}.{{0,100}}', text, re.DOTALL
                )
                context = context_pattern.group(0) if context_pattern else ""
                context = context.replace('\n', ' ').strip()
                concepts[term] = context[:200] + "..." if len(context) > 200 else context

        return concepts

    def add_page(self, page: WikiPage):
        """Add or update a wiki page"""
        self.pages[page.id] = page
        self.doc_index[page.document_id].append(page.id)
        self.type_index[page.page_type].append(page.id)

    def get_page(self, page_id: str) -> Optional[WikiPage]:
        return self.pages.get(page_id)

    def get_document_pages(self, document_id: str) -> List[WikiPage]:
        return [self.pages[pid] for pid in self.doc_index.get(document_id, [])
                if pid in self.pages]

    def search_pages(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search wiki pages by keyword"""
        query_lower = query.lower()
        scored = []
        for pid, page in self.pages.items():
            score = 0
            if query_lower in page.title.lower():
                score += 3
            if query_lower in page.content.lower():
                score += page.content.lower().count(query_lower)
            if query_lower in page.metadata.get("filename", "").lower():
                score += 2
            if score > 0:
                scored.append((score, pid, page))

        scored.sort(key=lambda x: -x[0])
        return [
            {
                "page_id": page.id,
                "title": page.title,
                "type": page.page_type,
                "content": page.content[:300],
                "document_id": page.document_id,
                "score": round(score / max(s for s, _, _ in scored), 3) if scored else 0
            }
            for score, pid, page in scored[:top_k]
        ]

    def get_stats(self) -> Dict:
        return {
            "total_pages": len(self.pages),
            "by_type": {t: len(pids) for t, pids in self.type_index.items()},
            "documents": len(self.doc_index)
        }

    def clear(self):
        """Clear all wiki pages and reset indexes"""
        self.pages.clear()
        self.doc_index.clear()
        self.type_index.clear()
        self._save()

    def _save(self):
        """Save wiki to disk"""
        data = {
            "pages": {
                pid: {
                    "id": page.id,
                    "title": page.title,
                    "page_type": page.page_type,
                    "content": page.content,
                    "document_id": page.document_id,
                    "metadata": page.metadata,
                    "links": page.links,
                    "created_at": page.created_at,
                    "updated_at": page.updated_at
                }
                for pid, page in self.pages.items()
            }
        }
        with open(os.path.join(self.persist_dir, "wiki_data.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        """Load wiki from disk"""
        wiki_path = os.path.join(self.persist_dir, "wiki_data.json")
        if os.path.exists(wiki_path):
            try:
                with open(wiki_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for pid, page_data in data.get("pages", {}).items():
                    page = WikiPage(
                        page_id=page_data["id"],
                        title=page_data["title"],
                        page_type=page_data["page_type"],
                        content=page_data["content"],
                        document_id=page_data.get("document_id", ""),
                        metadata=page_data.get("metadata", {})
                    )
                    page.links = page_data.get("links", [])
                    # 恢复持久化的时间戳，避免每次启动后任意一次保存把全部页面时间重置为 now
                    page.created_at = page_data.get("created_at") or page.created_at
                    page.updated_at = page_data.get("updated_at") or page.updated_at
                    self.pages[pid] = page
                    self.doc_index[page.document_id].append(pid)
                    self.type_index[page.page_type].append(pid)
            except Exception:
                pass
