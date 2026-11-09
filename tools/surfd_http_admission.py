#!/usr/bin/env python3
"""Cooperative WSGI request admission using the existing generation fence.

Install through Gunicorn's post_worker_init config hook, before its request loop:
    install(worker, guard=sealed_guard_module, state_dir=sealed_state_path,
            generation=sealed_generation, manifest_sha256=sealed_manifest_hash)

The config, this module and guard must be sealed deployment inputs. This is not a
sandbox or a replacement for source/actor validation, startup data preservation,
candidate lifetime drain, or an external acceptance receipt. No environment or
alternate application/command argument selects the fence.
"""
import hashlib
import json
import math
import os


class LeasedResponse:
    """Keep one request's independent lock through iteration and response close."""

    def __init__(self, response, fd):
        self.response = response
        self.fd = fd
        self.iterator = None

    def __iter__(self):
        return self

    def __next__(self):
        try:
            if self.iterator is None:
                self.iterator = iter(self.response)
            return next(self.iterator)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.fd is None:
            return
        fd, self.fd = self.fd, None
        try:
            close = getattr(self.response, 'close', None)
            if close is not None:
                close()
        finally:
            os.close(fd)


class Admission:
    def __init__(self, application, *, guard, state_dir, generation,
                 manifest_sha256, timeout=0.25):
        guard.require(os.name == 'posix', 'POSIX request admission required')
        guard.require(math.isfinite(timeout) and 0 <= timeout <= 1,
                      'bounded request admission timeout required')
        self.guard = guard
        self.root = guard.plain_path(str(state_dir))
        guard.secure_stat(self.root.stat(), True)
        manifest_path = guard.plain_path(str(self.root / 'manifest.json'))
        fd = os.open(manifest_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            guard.secure_stat(os.fstat(source.fileno()))
            raw = source.read(65537)
        guard.require(len(raw) <= 65536 and
                      hashlib.sha256(raw).hexdigest() == manifest_sha256,
                      'request manifest source binding mismatch')
        self.manifest = guard.manifest_check(json.loads(raw))
        guard.require(self.manifest['generation'] == generation,
                      'request generation mismatch')
        self.closure = guard.state_read(self.root, self.manifest)['closure']
        self.application = application
        self.timeout = timeout

    def state(self):
        value = self.guard.state_read(self.root, self.manifest)
        self.guard.require(value['closure'] == self.closure,
                           'request worker closure changed')
        return value

    @staticmethod
    def refused(environ, start_response):
        body = b'Backend admission closed\n'
        start_response('503 Service Unavailable', [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(body))), ('Retry-After', '1'),
            ('Cache-Control', 'no-store')])
        return [] if environ.get('REQUEST_METHOD') == 'HEAD' else [body]

    def __call__(self, environ, start_response):
        import fcntl
        fd = None
        health = (environ.get('REQUEST_METHOD') == 'GET' and
                  environ.get('PATH_INFO') == '/health' and
                  not environ.get('QUERY_STRING'))
        try:
            if health:
                # The sole CLOSED exception calls the existing read-only health
                # route, never a query/method-selected ordinary endpoint.
                self.state()
            else:
                # A separate open description is essential for concurrent gthread
                # requests: unlocking one must not release a sibling's lease.
                fd = self.guard.lock_file(self.root, 'admission.lock')
                self.guard.acquire(fd, fcntl.LOCK_SH, self.timeout)
                self.guard.require(self.state()['admission'] == 'OPEN',
                                   'CLOSED request refused before application')
        except (OSError, ValueError, KeyError, TypeError):
            if fd is not None:
                os.close(fd)
            return self.refused(environ, start_response)
        if health:
            return self.application(environ, start_response)
        try:
            response = self.application(environ, start_response)
            return LeasedResponse(response, fd)
        except BaseException:
            os.close(fd)
            raise


def install(worker, **binding):
    """Gunicorn 20.1 calls this after load_wsgi, before the worker request loop."""
    if isinstance(worker.wsgi, Admission):
        raise ValueError('request admission already installed')
    worker.wsgi = Admission(worker.wsgi, **binding)
