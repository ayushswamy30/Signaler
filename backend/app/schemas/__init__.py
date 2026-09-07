"""Pydantic schemas: the request and response contract of the HTTP API.

Kept separate from ``app/models``: an ORM model describes a table, a schema
describes what crosses the wire. Merging them would leak columns such as
``password_hash`` into responses by default.
"""
