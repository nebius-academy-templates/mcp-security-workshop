"""Entrypoint: `python -m fake_authz_server` (serves on http://localhost:9000)."""

from fake_authz_server.app import main

if __name__ == "__main__":
    main()
