from __future__ import annotations

from app.models.mail import MailThreadStaging
from app.services.mail_vector_index import (
    MailVectorHit,
    MailVectorSearchStore,
    _thread_metadata,
    build_mail_vector_document,
    merge_vector_and_text_results,
)


def test_mail_vector_document_uses_structured_fields_without_raw_refs() -> None:
    thread = _thread(
        "thread-1",
        subject="카카오 캠페인 리포트 요청",
        summary="성과 리포트와 다음 액션 플랜을 요청한 메일",
        metadata_json='{"body_sample":"원문 샘플은 검색 문서에 넣지 않는다","extracted_actions":[{"text":"액션 플랜 작성"}],"extracted_due_dates":[{"text":"금요일"}],"structure_warnings":[]}',
        attachments_json='[{"title":"report.xlsx","extension":"xlsx","summary":"CTR, CPA 지표"}]',
    )

    document = build_mail_vector_document(thread)

    assert "카카오 캠페인 리포트 요청" in document
    assert "액션 플랜 작성" in document
    assert "CTR, CPA 지표" in document
    assert "gmail:secret-source-ref" not in document
    assert "원문 샘플" not in document


def test_mail_vector_document_prefers_managed_core_text() -> None:
    thread = _thread(
        "thread-1",
        subject="제목",
        summary="요약",
        metadata_json='{"mail_core_text":"메일+첨부 통합 업무 문서","primary_context_source":"attachment","attachment_signals":{"count":1,"summary_status":"summarized"}}',
    )

    document = build_mail_vector_document(thread)
    metadata = _thread_metadata(thread)

    assert document == "메일+첨부 통합 업무 문서"
    assert metadata["source"] == "mail"
    assert metadata["primary_context_source"] == "attachment"
    assert metadata["attachment_count"] == "1"


def test_merge_vector_and_text_results_prioritizes_semantic_hit() -> None:
    semantic = _thread("semantic", subject="주간 보고서 액션 플랜", summary="다음 주 실행 계획을 정리해 달라는 요청")
    lexical = _thread("lexical", subject="메일 검색 테스트", summary="검색이라는 단어만 포함된 일반 메일")
    vector_hits = [
        MailVectorHit(
            thread_id="semantic",
            vector_score=0.92,
            distance=0.08,
            document="요청사항: 다음 주 액션 플랜 작성",
            evidence=[{"field": "semantic_vector", "snippet": "다음 주 액션 플랜 작성"}],
        )
    ]
    text_items = [{
        "id": "lexical",
        "thread_id": "lexical",
        "subject": "메일 검색 테스트",
        "sender": "sender@example.com",
        "received_at": "2026-05-12T00:00:00+00:00",
        "summary": "검색이라는 단어만 포함된 일반 메일",
        "category": "일반 업무",
        "attachments": [],
        "metadata": {},
        "score": 20,
        "matched_fields": ["summary"],
        "evidence": [{"field": "summary", "snippet": "검색이라는 단어"}],
    }]

    results = merge_vector_and_text_results(
        [semantic, lexical],
        vector_hits=vector_hits,
        text_items=text_items,
        limit=2,
    )

    assert [item["thread_id"] for item in results] == ["semantic", "lexical"]
    assert results[0]["retrieval"]["mode"] == "hybrid_vector"
    assert "semantic_vector" in results[0]["matched_fields"]


def test_vector_store_skips_reindex_when_manifest_is_current(tmp_path) -> None:
    collection = FakeCollection()
    provider = FakeEmbeddingProvider()
    store = MailVectorSearchStore(
        str(tmp_path),
        embedding_provider=provider,
        client_factory=lambda _path: FakeClient(collection),
    )
    threads = [_thread("thread-1", subject="카카오 리포트", summary="성과 보고 요청")]

    store.search(run_id="run-1", threads=threads, query="카카오 보고", limit=1)
    store.search(run_id="run-1", threads=threads, query="카카오 보고", limit=1)

    assert collection.upsert_count == 1


def test_index_run_deletes_stale_run_documents(tmp_path) -> None:
    collection = FakeCollection()
    collection.ids = ["managed", "excluded"]
    collection.documents = ["managed doc", "excluded doc"]
    collection.metadatas = [
        {"thread_id": "managed", "run_id": "run-1"},
        {"thread_id": "excluded", "run_id": "run-1"},
    ]
    store = MailVectorSearchStore(
        str(tmp_path),
        embedding_provider=FakeEmbeddingProvider(),
        client_factory=lambda _path: FakeClient(collection),
    )

    store.index_run(run_id="run-1", threads=[_thread("managed", subject="업무", summary="관리 대상")])

    assert collection.delete_count == 1
    assert collection.ids == ["managed"]


def _thread(
    thread_id: str,
    *,
    subject: str,
    summary: str,
    metadata_json: str = "{}",
    attachments_json: str = "[]",
) -> MailThreadStaging:
    return MailThreadStaging(
        id=thread_id,
        run_id="run-1",
        project_id="project-1",
        user_id="user-1",
        source_ref="gmail:secret-source-ref",
        subject=subject,
        sender="sender@example.com",
        recipients_json='["me@example.com"]',
        received_at="2026-05-12T00:00:00+00:00",
        summary=summary,
        category="일반 업무",
        attachments_json=attachments_json,
        inclusion_decision="allowed",
        metadata_json=metadata_json,
    )


class FakeEmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _text in texts]


class FakeClient:
    def __init__(self, collection: "FakeCollection") -> None:
        self.collection = collection

    def get_or_create_collection(self, **_kwargs):
        return self.collection


class FakeCollection:
    def __init__(self) -> None:
        self.upsert_count = 0
        self.delete_count = 0
        self.ids: list[str] = []
        self.documents: list[str] = []
        self.metadatas: list[dict[str, str]] = []

    def delete(self, *, where) -> None:
        self.delete_count += 1
        run_id = str((where or {}).get("run_id") or "")
        keep = [index for index, metadata in enumerate(self.metadatas) if metadata.get("run_id") != run_id]
        self.ids = [self.ids[index] for index in keep]
        self.documents = [self.documents[index] for index in keep]
        self.metadatas = [self.metadatas[index] for index in keep]

    def upsert(self, *, ids, documents, embeddings, metadatas) -> None:
        self.upsert_count += 1
        self.ids = list(ids)
        self.documents = list(documents)
        self.metadatas = list(metadatas)

    def count(self) -> int:
        return len(self.ids)

    def query(self, **_kwargs):
        return {
            "ids": [self.ids],
            "documents": [self.documents],
            "metadatas": [self.metadatas],
            "distances": [[0.1 for _id in self.ids]],
        }
