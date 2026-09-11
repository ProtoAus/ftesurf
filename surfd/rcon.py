#!/usr/bin/env python3
"""
rcon.py -- a minimal, deliberately narrow FTE/QuakeWorld rcon client.

This is the admin panel's only channel to the game servers. There is no other
one: QuakeC cannot open a socket, so rcon is it.

READ THIS BEFORE ADDING A COMMAND
=================================

The engine's rcon handler reassembles arguments WITHOUT re-quoting them and
then feeds the result to the console command buffer (SVC_RemoteCommand,
engine/server/sv_main.c:4046-4068):

    for (i=2 ; i<Cmd_Argc() ; i++) {
        Q_strncatz(remaining, Cmd_Argv(i), sizeof(remaining));
        Q_strncatz(remaining, " ", sizeof(remaining));
    }
    Cbuf_AddText(remaining, rcon_level.ival);

Cmd_TokenizeString strips the quotes on the way in, and nothing puts them back
on the way out. So a single argument containing a semicolon or a newline
BECOMES A SECOND CONSOLE COMMAND:

    rcon <pass> say "hello; quit"
      -> argv(2)="say"  argv(3)="hello; quit"
      -> remaining = 'say hello; quit '
      -> Cbuf runs `say hello` AND THEN `quit`

That is command injection in the engine, reachable by anything that can get a
string into an rcon argument. It is not a hypothetical: the panel's map field,
hostname field and say field are all free text.

The mitigation lives HERE rather than in each caller, because a mitigation each
caller has to remember is one that some future caller will forget:

  * every argument is checked against SAFE_ARG before it is sent (send_argv),
  * `;`, newline, carriage return, quote, `$` and control characters are
    refused outright -- refused, not stripped, because silently mangling an
    admin's input is its own bug,
  * callers pass a LIST of already-separate arguments, never a command line,
    so there is no place for the caller to do its own quoting badly.

`$` is in the refused set because the console expands $variables
(Cmd_ExpandString), which is a second, quieter way to get unexpected text into
a command.

WHY THE HASHED FORM IS THE DEFAULT
==================================

sv_crypt_rcon defaults to "" (engine/server/sv_main.c:78), and Rcon_Validate
reads that as "accept either form" -- both the plaintext branch and the hashed
branch are entered when the string is empty. So the hashed form works against a
stock server with no configuration at all, and the password never appears on
the wire even once.

It also carries a timestamp that the server range-checks against
sv_crypt_rcon_clockskew (60s), which blunts replay. Note that cvar's NAME is
"sv_timestamplen", not "sv_crypt_rcon_clockskew" -- the C identifier and the
registered name disagree (sv_main.c:79). If you go looking for it on a running
server, look for sv_timestamplen.

Once this client is the only rcon user, set `sv_crypt_rcon 1` on the servers to
refuse the plaintext form entirely. That is a server-side change and belongs in
cfg/lobby.cfg, not here.

WHAT THIS DOES NOT DO
=====================

It does not authenticate the SERVER, and it cannot: rcon has no challenge and
no server signature (the engine's own comment, sv_main.c:3849-3854, says the
protocol sucks and lists this as reason 2). Replies are unauthenticated UDP and
any host that can reach our socket can forge one. That is tolerable only
because we exclusively talk to 127.0.0.1 -- see LOOPBACK_ONLY below, which is
enforced rather than assumed.
"""

import hashlib
import re
import socket
import threading
import time

# --------------------------------------------------------------------------
# The packet budget, and why it is not tuning
# --------------------------------------------------------------------------
#
# THE ENGINE COUNTS RCON AS A DDOS ATTACK, AND LOOPBACK IS NOT EXEMPT.
#
# SV_ConnectionlessPacket dispatches rcon through the same guard as an
# anonymous `getstatus` from the open internet (sv_main.c:4441-4444):
#
#     else if (!strcmp(c, "rcon"))
#     {
#         if (SV_DetectAmplificationDDOS())
#             SVC_RemoteCommand ();
#     }
#
# The guard runs BEFORE the password is looked at, so being authenticated buys
# nothing. Its only exemption is SV_Master_AddressIsMaster, which lives in the
# *other* throttle (SVC_ThrottleInfo, sv_main.c:4167) and is not consulted on
# this path at all. There is no carve-out for 127.0.0.1.
#
# The constants are compile-time, not cvars (sv_main.c:4197-4199):
#
#     dosattacker_limit      15          packets
#     dosattacker_period     30          seconds
#     dosattacker_blocktime  60*60*24    ... a TWENTY-FOUR HOUR block
#
# and the block extends itself. Once over the limit, each further packet adds
# period/limit == 2.0s to the deadline (sv_main.c:4236-4237). Anything polling
# faster than one packet per two seconds pushes that deadline away faster than
# the clock advances, so the 24-hour block becomes an indefinite one. Nothing
# clears it but a restart -- the table is process-lifetime static state.
#
# The panel earned exactly that on its first run. Four commands per lobby every
# five seconds is 24 packets per 30s window against a limit of 15: blocked in
# about nineteen seconds, and never recovering while the page stayed open.
#
# So this budget is not politeness. It is enforced HERE, in the one place every
# rcon packet passes through, rather than in the callers -- for the same reason
# the injection check is here: a rule each caller has to remember is one some
# future caller will forget.
#
# NOTE THE PROCESS ASSUMPTION: this counter is per Python process, and surfd
# runs `gunicorn --workers 1` (run.sh:31). Raising the worker count multiplies
# the real packet rate by the number of workers and silently eats the margin.
# If workers ever go up, this budget must come down, or move to shared state.

ENGINE_DOS_LIMIT = 15        # sv_main.c:4197  dosattacker_limit
ENGINE_DOS_PERIOD = 30.0     # sv_main.c:4198  dosattacker_period

# Our ceiling, per server port, over a sliding window of the engine's period.
# A sliding 8-per-30s cannot produce 15 in any fixed 30s window the engine
# might be measuring, so this holds with roughly 2x margin -- enough to absorb
# an admin clicking buttons while a refresh happens to land.
BUDGET_PACKETS = 8
BUDGET_PERIOD = ENGINE_DOS_PERIOD

# What the engine sends at the exact moment it decides to block you
# (sv_main.c:4231). It says it once and is silent forever after, so this
# recognises the transition, not the state.
DDOS_REPLY = "Probable ddos amplification attack"

_budget_lock = threading.Lock()
_budget = {}                 # (host, port) -> [monotonic timestamps]

# Every argument must match this. Deliberately tight: alphanumerics, and the
# punctuation that map names, cvar names, hostnames and chat actually need.
# Space is allowed (so `say hello world` is one argument) but the injection
# characters are not.
SAFE_ARG = re.compile(r"^[A-Za-z0-9 _.:/+@!?,()\[\]{}=*<>%^&#~'-]*$")

# Refused explicitly so the error message can name the character.
FORBIDDEN = {
    ";": "semicolon (would start a second console command)",
    "\n": "newline (would start a second console command)",
    "\r": "carriage return",
    '"': "double quote (would break argument tokenisation)",
    "$": "dollar (the console expands $variables)",
    "\\": "backslash",
}

MAX_ARG_LEN = 128
MAX_ARGS = 16

# The engine truncates the reassembled command at 1024 bytes and logs
# "Rcon was too long" (sv_main.c:4054). Stay well under it.
MAX_COMMAND_LEN = 900

LOOPBACK_ONLY = True


class RconError(Exception):
    """Anything that stopped a command from being sent or answered."""


class RconUnsafe(RconError):
    """An argument was refused before it reached the network."""


class RconThrottled(RconError):
    """Refused locally to stay under the engine's amplification guard.

    This is a success, not a failure: the alternative to this exception is a
    24-hour block on a game server. Callers should cache harder, not retry.
    """


class RconBlocked(RconError):
    """The server said it is now treating us as a DDoS source."""


def budget_take(host, port, now=None):
    """Claim one packet's worth of budget for one server, or refuse.

    A sliding window rather than the engine's fixed one, because a sliding
    window is strictly the safer of the two: if no 30-second interval anywhere
    contains more than BUDGET_PACKETS, then neither does whichever fixed window
    the engine happens to be counting in.
    """
    now = time.monotonic() if now is None else now
    key = (host, int(port))
    with _budget_lock:
        sent = _budget.setdefault(key, [])
        cutoff = now - BUDGET_PERIOD
        while sent and sent[0] <= cutoff:
            sent.pop(0)
        if len(sent) >= BUDGET_PACKETS:
            wait = max(0.0, sent[0] + BUDGET_PERIOD - now)
            raise RconThrottled(
                "rcon budget for port %d is spent (%d packets per %gs); next "
                "slot in %.0fs. This cap keeps us under the engine's 24-hour "
                "amplification block -- see the essay in rcon.py."
                % (int(port), BUDGET_PACKETS, BUDGET_PERIOD, wait)
            )
        sent.append(now)
        return BUDGET_PACKETS - len(sent)


def budget_left(host, port, now=None):
    """How many packets are still available for this server. Never raises."""
    now = time.monotonic() if now is None else now
    with _budget_lock:
        sent = _budget.get((host, int(port)), [])
        fresh = [t for t in sent if t > now - BUDGET_PERIOD]
        return max(0, BUDGET_PACKETS - len(fresh))


def budget_reset():
    """Drop all accounting. For tests only."""
    with _budget_lock:
        _budget.clear()


def check_arg(arg):
    """Raise RconUnsafe unless `arg` is safe to pass through rcon.

    Refuses rather than sanitises. A silently-stripped semicolon turns
    `say "5; 4; 3; go"` into `say 5 4 3 go`, which is a confusing bug; a
    refusal is a message the admin can act on.
    """
    if not isinstance(arg, str):
        raise RconUnsafe("argument %r is not a string" % (arg,))
    if len(arg) > MAX_ARG_LEN:
        raise RconUnsafe(
            "argument is %d characters; the limit is %d" % (len(arg), MAX_ARG_LEN)
        )
    for bad, why in FORBIDDEN.items():
        if bad in arg:
            raise RconUnsafe("argument contains a %s" % why)
    for ch in arg:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            raise RconUnsafe("argument contains a control character (0x%02x)" % ord(ch))
    if not SAFE_ARG.match(arg):
        raise RconUnsafe("argument contains a character that is not allowed")
    return arg


def _timehex(now):
    """Encode a unix time the way Rcon_Validate decodes it.

    sv_main.c:3882-3888 reads the timestamp as hex nibble pairs where each PAIR
    is a byte but the BYTES run little-endian:

        i even -> nibble << ((i/2)*8 + 4)      high nibble of byte i/2
        i odd  -> nibble << ((i/2)*8 + 0)      low  nibble of byte i/2

    which is exactly "the low 32 bits, little-endian, two hex digits per byte".
    Four bytes is what ezquake sends and is what the loop's `i < 16` bound
    accommodates; it is good until 2106.
    """
    return (now & 0xFFFFFFFF).to_bytes(4, "little").hex()


def hashed_password(realpass, argv_tail, now):
    """Build the "[sha1][timehex]" password argument for the hashed form.

    The digest covers, in order (sv_main.c:3894-3907):

        "rcon" " " <realpass> <timehex> " " then <arg> " " for each argument

    Note the trailing space after EVERY argument, including the last -- the
    engine's comment calls it out because it is easy to leave off.
    """
    h = hashlib.sha1()
    h.update(b"rcon")
    h.update(b" ")
    h.update(realpass.encode("utf-8"))
    th = _timehex(now)
    h.update(th.encode("ascii"))
    h.update(b" ")
    for arg in argv_tail:
        h.update(arg.encode("utf-8"))
        h.update(b" ")
    return h.hexdigest() + th


def _quote(arg):
    """Render one argument for Cmd_TokenizeString.

    Anything with a space needs quotes to survive tokenisation as a single
    argument. check_arg has already guaranteed there is no quote character
    inside, so this cannot produce an unbalanced string.
    """
    return '"%s"' % arg if (" " in arg or arg == "") else arg


class Rcon:
    """One game server's rcon endpoint."""

    def __init__(self, host, port, password, crypt=True, timeout=1.2,
                 collect_for=0.35):
        if LOOPBACK_ONLY and host not in ("127.0.0.1", "::1", "localhost"):
            # The panel is a public login. If a bug or a config edit ever
            # pointed it at a remote host, the rcon password would leave this
            # machine in a packet nothing authenticates. Refuse structurally.
            raise RconError(
                "refusing to send rcon to %r: this client is loopback-only "
                "(see the essay at the top of rcon.py)" % (host,)
            )
        self.host = host
        self.port = int(port)
        self.password = password or ""
        self.crypt = crypt
        self.timeout = timeout
        # How long to keep listening AFTER the first packet. A long reply is
        # split across several connectionless packets by SV_FlushRedirect
        # (engine/server/sv_send.c:57-80) and they arrive back to back; there
        # is no end-of-reply marker in the protocol, so a short quiet period is
        # the only available terminator.
        self.collect_for = collect_for

    def execute(self, argv, expect_reply=True):
        """Run one command. `argv` is a list of already-separated arguments.

        Returns the server's printed reply as text (possibly empty). Raises
        RconUnsafe if any argument is refused, RconError on a transport
        problem.
        """
        if not self.password:
            raise RconError("no rcon password configured")
        if not argv:
            raise RconError("empty command")
        if len(argv) > MAX_ARGS:
            raise RconError("too many arguments (%d)" % len(argv))
        argv = [check_arg(a) for a in argv]

        if self.crypt:
            passarg = hashed_password(self.password, argv, int(time.time()))
        else:
            passarg = check_arg(self.password)

        line = "rcon %s %s" % (passarg, " ".join(_quote(a) for a in argv))
        if len(line) > MAX_COMMAND_LEN:
            raise RconError("command is too long (%d bytes)" % len(line))
        packet = b"\xff\xff\xff\xff" + line.encode("utf-8")

        # Claimed BEFORE the socket exists, so a refusal costs nothing and
        # cannot half-send. See the budget essay at the top of this file: going
        # over is a 24-hour block on a live game server, not a slow reply.
        budget_take(self.host, self.port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(self.timeout)
            try:
                sock.sendto(packet, (self.host, self.port))
            except OSError as exc:
                raise RconError("cannot reach %s:%d (%s)"
                                % (self.host, self.port, exc)) from exc
            if not expect_reply:
                return ""
            reply = self._collect(sock)
            if DDOS_REPLY in reply:
                raise RconBlocked(
                    "port %d has blocked us as a presumed amplification "
                    "attack. The engine's block lasts 24 hours and extends "
                    "itself on every further packet, so only restarting that "
                    "lobby clears it." % (self.port,)
                )
            return reply
        finally:
            sock.close()

    def _collect(self, sock):
        chunks = []
        deadline = None
        while True:
            try:
                data, _ = sock.recvfrom(8192)
            except socket.timeout:
                break
            except OSError as exc:
                raise RconError("receive failed (%s)" % exc) from exc
            chunks.append(self._decode(data))
            # After the first packet, only wait a short while for more.
            if deadline is None:
                deadline = time.monotonic() + self.collect_for
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
        return "".join(chunks)

    @staticmethod
    def _decode(data):
        """Unwrap one connectionless reply packet.

        SV_FlushRedirect emits  ff ff ff ff 'n' <text> 00  (A2C_PRINT is 'n',
        common/protocol.h:262). Anything else is not ours; return it raw rather
        than dropping it, so an unexpected reply shows up in the panel instead
        of vanishing.
        """
        if data[:4] == b"\xff\xff\xff\xff":
            body = data[4:]
            if body[:1] == b"n":
                body = body[1:]
        else:
            body = data
        return body.rstrip(b"\x00").decode("utf-8", "replace")


# --------------------------------------------------------------------------
# Output hygiene
# --------------------------------------------------------------------------

# Dotted-quad, optionally with :port. Deliberately greedy about what counts as
# an address: over-redacting an rcon reply costs nothing, under-redacting puts
# a player's IP on a web page.
_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?\b")
# A bare IPv6 or an IPv4-mapped one. Loose on purpose, same reasoning.
_IPV6 = re.compile(r"\b(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f:.]{1,39}\b")

_COLOUR = re.compile(r"\^(?:[0-9]|x[0-9A-Fa-f]{3}|b|s|r|a|m)")
# The engine's ^[ ... ^] tooltip markup, used by `status` for its column
# headers. Strip the markup, keep the visible text before the first backslash.
_TIP = re.compile(r"\^\[(.*?)(?:\\.*?)?\^\]")


def redact(text):
    """Remove anything that identifies where a player is connecting from.

    The panel shows player NAMES to an authenticated admin, which is not a
    disclosure that needs a terms change. Showing IPs would be. `status`
    prints an address column for every client (sv_ccmds.c:2645-2652 and the
    C_ADDRESS/C_ADDRESS2 columns at :2674/:2683), so anything derived from
    `status` must pass through here before it reaches a template.

    This is defence in depth, not the primary control: the panel does not put
    raw rcon output on the page. It exists so that a future feature that
    forgets is still safe.
    """
    text = _IPV4.sub("[addr]", text)
    text = _IPV6.sub("[addr]", text)
    return text


def strip_colours(text):
    """Drop FTE colour codes and tooltip markup so text renders as text."""
    text = _TIP.sub(r"\1", text)
    return _COLOUR.sub("", text)


def clean_reply(text):
    """What the panel is allowed to display from an rcon reply."""
    return redact(strip_colours(text))
