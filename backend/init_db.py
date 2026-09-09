from db import ensure_schema


def main():
    """Initialize the persistent chat tables used for sessions and messages."""
    ensure_schema()
    print("Database tables created successfully")


if __name__ == "__main__":
    main()