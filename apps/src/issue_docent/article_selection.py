from apps.src.repositories.issue_docent import ArticleForGeneration


MAX_ARTICLES_FOR_DEEP_BRIEF = 5


def select_articles_for_deep_brief(
    articles: list[ArticleForGeneration],
) -> list[ArticleForGeneration]:
    return sorted(articles, key=lambda article: article.article_order)[:MAX_ARTICLES_FOR_DEEP_BRIEF]
