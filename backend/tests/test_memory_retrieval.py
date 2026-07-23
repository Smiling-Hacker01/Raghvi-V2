"""Tests for semantic memory retrieval."""

import pytest

from app.services.memory.retrieval import TFIDFRetriever, get_retriever
from app.services.memory.service import MemoryService


class TestTFIDFRetriever:
    """Tests for TF-IDF retriever."""

    def test_tokenization_removes_stopwords(self):
        """Test that stopwords are removed."""
        retriever = TFIDFRetriever()

        tokens = retriever._tokenize("I love learning Rust programming")

        assert "i" not in tokens
        assert "learning" in tokens
        assert "rust" in tokens
        assert "programming" in tokens

    def test_tokenization_lowercase(self):
        """Test that tokenization is case-insensitive."""
        retriever = TFIDFRetriever()

        tokens1 = retriever._tokenize("RUST Programming")
        tokens2 = retriever._tokenize("rust programming")

        assert tokens1 == tokens2

    def test_calculate_tf(self):
        """Test TF calculation."""
        retriever = TFIDFRetriever()

        tokens = ["rust", "python", "rust", "rust"]
        tf = retriever._calculate_tf(tokens)

        # rust appears 3 times (max), python 1 time
        assert tf["rust"] == 1.0  # Max frequency
        assert tf["python"] == 1 / 3  # 1/3 of max

    def test_calculate_idf(self):
        """Test IDF calculation."""
        retriever = TFIDFRetriever()

        documents = [
            ["rust", "programming"],
            ["rust", "learning"],
            ["python", "learning"],
        ]

        idf = retriever._calculate_idf(documents)

        # "rust" appears in 2/3 docs → idf = log(3/2)
        # "learning" appears in 2/3 docs → idf = log(3/2)
        # "python" appears in 1/3 docs → idf = log(3/1) = log(3) (highest)
        assert idf["python"] > idf["rust"]

    def test_tfidf_scoring(self):
        """Test TF-IDF scoring."""
        retriever = TFIDFRetriever()

        query_tf = {"rust": 1.0}
        doc_tf_match = {"rust": 1.0, "other": 0.5}
        doc_tf_nomatch = {"python": 1.0}
        idf = {"rust": 1.5, "python": 2.0, "other": 0.5}

        score_match = retriever._calculate_tfidf_score(query_tf, doc_tf_match, idf)
        score_nomatch = retriever._calculate_tfidf_score(query_tf, doc_tf_nomatch, idf)

        assert score_match > score_nomatch
        assert score_nomatch == 0.0

    @pytest.mark.asyncio
    async def test_retrieve_relevant_memories(self, test_db, test_user):
        """Test retrieving relevant memories."""
        async with test_db() as session:
            # Create memories
            mem1, _, _ = await MemoryService.create_memory(
                user_id=test_user.id,
                content="I'm learning Rust programming",
                session=session,
            )
            mem2, _, _ = await MemoryService.create_memory(
                user_id=test_user.id,
                content="I work at Google",
                session=session,
            )
            mem3, _, _ = await MemoryService.create_memory(
                user_id=test_user.id,
                content="I love hiking in nature",
                session=session,
            )

            await session.commit()

            # Retrieve memories matching "Rust programming"
            retriever = TFIDFRetriever()
            results = await retriever.retrieve(
                user_id=test_user.id,
                query="How do I handle Rust macros?",
                session=session,
            )

            # mem1 should be first (contains "Rust")
            assert len(results) > 0
            assert results[0].id == mem1.id

    @pytest.mark.asyncio
    async def test_retrieve_no_memories(self, test_db, test_user):
        """Test retrieval when no memories match."""
        async with test_db() as session:
            retriever = TFIDFRetriever()
            results = await retriever.retrieve(
                user_id=test_user.id,
                query="something",
                session=session,
            )

            assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_top_k_limit(self, test_db, test_user):
        """Test that retrieval respects top_k limit."""
        async with test_db() as session:
            # Create 15 memories
            for i in range(15):
                await MemoryService.create_memory(
                    user_id=test_user.id,
                    content=f"Memory {i} with programming",
                    session=session,
                )

            await session.commit()

            # Retrieve with top_k=5
            retriever = TFIDFRetriever(top_k=5)
            results = await retriever.retrieve(
                user_id=test_user.id,
                query="programming",
                session=session,
            )

            assert len(results) <= 5

    def test_retriever_singleton(self):
        """Test get_retriever pattern."""
        retriever1 = get_retriever()
        retriever2 = get_retriever()

        # Different instances (stateless)
        assert retriever1.top_k == retriever2.top_k

    @pytest.mark.asyncio
    async def test_retrieve_with_stopwords_filtered(self, test_db, test_user):
        """Test that stopwords don't affect relevance."""
        async with test_db() as session:
            # Memory: just content word
            mem, _, _ = await MemoryService.create_memory(
                user_id=test_user.id,
                content="I am learning Python",
                session=session,
            )

            await session.commit()

            # Query with many stopwords
            retriever = TFIDFRetriever()
            results = await retriever.retrieve(
                user_id=test_user.id,
                query="I am and or but trying to learn Python",
                session=session,
            )

            # Should still find the memory (stopwords ignored)
            assert len(results) > 0
            assert results[0].id == mem.id
