"""뉴스 소스 모듈.

모든 소스는 search(query) 함수를 제공하고, PRD 7.1절 articles 항목과 같은 형태의
dict 리스트를 돌려준다. keywords/categories/score 는 collector 가 채운다.

    {
        "id": str, "title": str, "url": str, "source": str,
        "published_at": str | None (KST ISO 8601), "snippet": str, "provider": str,
    }
"""
