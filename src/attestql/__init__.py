"""Audit text-to-SQL gold and predictions on PostgreSQL or SQLite with typed replay evidence.

``audit`` is the command and its backend, ``evidence`` the record, serializer and comparator it
writes and reads, ``kernel`` the shared result types. ADR-0013 records the decision this package
implements.
"""
