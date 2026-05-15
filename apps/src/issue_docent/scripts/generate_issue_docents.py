import argparse
import asyncio

from apps.src.repositories.issue_docent import IssueDocentRepository
from apps.src.config.database import AsyncSessionLocal
from apps.src.services.issue_docent.generation_service import IssueDocentGenerationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Issue Docent content from clusters.")
    parser.add_argument("--cluster-id", type=int, help="Generate content for one cluster.")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of target clusters to process in batch mode.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate and overwrite existing issue_docent rows for selected clusters.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the graph and print the generated title without writing issue_docent rows.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    async with AsyncSessionLocal() as session:
        service = IssueDocentGenerationService(IssueDocentRepository(session))
        if args.cluster_id is not None:
            results = [
                await service.generate_for_cluster(
                    args.cluster_id,
                    force=args.force,
                    dry_run=args.dry_run,
                )
            ]
        else:
            results = await service.generate_batch(
                limit=args.limit,
                force=args.force,
                dry_run=args.dry_run,
            )

    for result in results:
        print(
            {
                "cluster_id": result.cluster_id,
                "issue_docent_id": result.issue_docent_id,
                "status": result.status,
                "title": result.title,
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
