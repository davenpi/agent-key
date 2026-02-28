"""Application entrypoint."""


def main() -> None:
    """Run a minimal CLI entrypoint.

    Returns
    -------
    None
        Prints the configured application import path.
    """
    print("Run with: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
