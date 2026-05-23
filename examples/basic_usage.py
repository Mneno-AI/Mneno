from mneno import MemoryClient


def main() -> None:
    client = MemoryClient()
    client.add("The user is building Mneno, an SDK for explainable AI memory.")

    results = client.search("What is the user building?")
    for memory in results:
        print(memory.content)


if __name__ == "__main__":
    main()
