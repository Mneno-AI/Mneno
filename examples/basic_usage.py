from mneno import MemoryClient


def main() -> None:
    client = MemoryClient()
    client.add(
        "The user is building Mneno, a Python SDK for explainable AI memory.",
        memory_type="semantic",
        importance=0.9,
        source="project-brief",
        tags=["project", "mneno"],
    )
    client.add(
        "The current task is to build the first local memory engine.",
        memory_type="operational",
        importance=0.8,
        tags=["task", "mvp"],
    )
    client.add(
        "The user prefers a lightweight Python-first SDK with no provider dependencies in core.",
        memory_type="preference",
        importance=0.85,
        tags=["preference", "architecture"],
    )

    results = client.search("What is the user building?")
    for result in results:
        print(f"#{result.rank}: {result.memory.content}")
        print(f"score={result.score.total}")
        for reason in result.score.reasons:
            print(f"- {reason}")


if __name__ == "__main__":
    main()
