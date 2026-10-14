#!/usr/bin/env python3
"""Executable *proposal*, not a native updater or a filesystem cleanup tool.

The signed-row table and protection classifications are trusted test inputs;
this model does not verify signatures, open files, install content or remove data.
Each yielded event is one process-interruption cut in the proposed protocol.
"""
from dataclasses import dataclass
import hashlib

MAX_ROWS = 8192
MAX_ATTEMPTS = 3


def digest(data):
    return hashlib.blake2b(data, digest_size=32).hexdigest()


@dataclass(frozen=True)
class Row:
    path: str
    hash: str
    size: int
    executable: bool = False

    @classmethod
    def for_bytes(cls, path, data, executable=False):
        return cls(path, digest(data), len(data), executable)


@dataclass(frozen=True)
class Journal:
    version: str
    attempts: int
    rows: tuple


@dataclass(frozen=True)
class Event:
    action: str
    hash: str = ''


class Refusal(Exception):
    pass


class Protocol:
    def __init__(self, version, signed_rows, journal, destinations, staged, preserved=()):
        self.version = version
        self.signed_rows = dict(signed_rows)
        self.journal = journal
        self.destinations = dict(destinations)
        self.staged = dict(staged)
        self.preserved = set(preserved)
        self.unreadable_destinations = set()
        self.unreadable_objects = set()
        self.held_objects = set()
        self.linked_objects = set()
        self.temp = None
        self.ledger_version = 'old'
        self.certificate = None
        self.removed = []

    def validate(self):
        j = self.journal
        if j is None:
            return
        if (j.version != self.version or type(j.attempts) is not int or
                not 1 <= j.attempts <= MAX_ATTEMPTS or not 1 <= len(j.rows) <= MAX_ROWS):
            raise Refusal('invalid transaction metadata')
        seen = set()
        for row in j.rows:
            if row.path in seen or self.signed_rows.get(row.path) != row:
                raise Refusal('duplicate or unsigned candidate tuple')
            seen.add(row.path)
            if row.hash in self.linked_objects:
                raise Refusal('linked candidate path')
            if row.path in self.unreadable_destinations:
                raise Refusal('unreadable destination classification')

    def pending(self):
        if self.journal is None:
            return ()
        return tuple(row for row in self.journal.rows if row.path not in self.preserved and
                     not self.matches(self.destinations.get(row.path), row))

    @staticmethod
    def matches(data, row):
        return data is not None and len(data) == row.size and digest(data) == row.hash

    def new_apply_allowed(self):
        # A retained generation cannot be silently overwritten by a newer plan.
        return self.journal is None

    def pass_events(self, fail_publication=False, content_admitted=False, fail_drop=False):
        """One retirement pass AFTER content classification/installation.

        Pending content still refuses at its existing budget. content_admitted
        represents an admitted content pass that has now landed all destinations;
        its bumped attempt must be published even if only cleanup remains. An
        already-complete set may retry cleanup at attempts3 without admission.
        Installation/admission itself is not modeled. Consumers can stop after
        any event and restart with a fresh iterator over persistent state.
        """
        self.validate()
        if self.journal is None:
            yield Event('no-authority')
            return
        initial = self.journal
        pending = self.pending()
        if not pending:
            if any(path in self.unreadable_destinations for path in self.signed_rows):
                raise Refusal('unreadable full signed installation')
            if not all(row.path in self.preserved or self.matches(self.destinations.get(row.path), row)
                       for row in self.signed_rows.values()):
                raise Refusal('full signed installation incomplete')
        if pending or content_admitted:
            if initial.attempts == MAX_ATTEMPTS:
                raise Refusal('content retry budget exhausted')
            # Both live/cold reduced writers must retain the original row superset.
            self.temp = Journal(initial.version, initial.attempts + 1, initial.rows)
            yield Event('temp-written')
            if fail_publication:
                raise Refusal('journal replacement failed')
            self.journal = self.temp
            self.temp = None
            yield Event('published')
        if not pending:
            self.ledger_version = initial.version
            self.certificate = initial.version
            yield Event('content-complete')

        for row in initial.rows:
            # Recheck authority and shared references at the destructive seam.
            self.validate()
            if self.journal is None or row not in self.journal.rows:
                raise Refusal('candidate authority disappeared')
            current_pending = self.pending()
            if any(other.hash == row.hash for other in current_pending):
                continue
            if row.hash not in self.staged:
                continue  # modeled OS-confirmed absence, not a failed read
            data = self.staged[row.hash]
            if (row.hash in self.unreadable_objects or row.hash in self.held_objects or
                    not self.matches(data, row)):
                yield Event('retained', row.hash)
                continue
            del self.staged[row.hash]
            self.removed.append(row.hash)
            yield Event('removed', row.hash)

        # Existing failed temps are not retirement candidates and are never erased.
        self.validate()
        if not self.pending() and all(row.hash not in self.staged for row in initial.rows):
            if fail_drop:
                yield Event('authority-drop-failed')
            else:
                self.journal = None
                yield Event('authority-dropped')
        else:
            yield Event('authority-retained')
