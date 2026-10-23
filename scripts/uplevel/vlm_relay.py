"""The two-hop VLM relay: a container-facing TCP half and a host-facing Unix half.

O2.5 item 1's venue fix (ruling 287). A GPU host where ``agent-gpu`` publishes the VLM
on the host's loopback only cannot hand that address to a container on a rootless-Podman
bridge network: the alias resolves there to a refused LAN address (the maui run's
measured failure), and the gateway address lives only inside the engine's rootless
network namespace, unreachable to the host. So the run relays with two halves of the
same stdlib script:

* ``tcp2unix <host:port> <socket>`` runs as the ``agent-gpu-relay`` compose service
  (inside the stack's own network): accepts TCP on ``0.0.0.0:<port>``, hands each
  connection over the run-dir Unix socket.
* ``unix2tcp <socket> <host:port>`` runs as a thread-pair in the harness process
  (host namespace): accepts on that socket, dials ``127.0.0.1:<pool port>`` — the
  loopback the lease published. The VLM keeps publishing loopback only.

Both halves are this file, copied into the run directory at arm time; nothing persists
beyond the run.
"""

import socket
import sys
import threading
from pathlib import Path

CHUNK = 65536
BACKLOG = 16


def pipe(a: socket.socket, b: socket.socket) -> None:
    try:
        while data := a.recv(CHUNK):
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _dial_unix(target: str) -> socket.socket:
    s = socket.socket(socket.AF_UNIX)
    s.connect(target)
    return s


def _dial_tcp(target: str) -> socket.socket:
    host, port = target.rsplit(":", 1)
    return socket.create_connection((host, int(port)))


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 3 or args[0] not in ("tcp2unix", "unix2tcp"):
        raise SystemExit(
            "usage: vlm_relay.py tcp2unix <host:port> <socket>\n"
            "       vlm_relay.py unix2tcp <socket> <host:port>"
        )
    mode, listen, target = args
    if mode == "tcp2unix":
        host, port = listen.rsplit(":", 1)
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, int(port)))
    else:
        sock = Path(listen)
        if sock.exists():
            sock.unlink()
        srv = socket.socket(socket.AF_UNIX)
        srv.bind(listen)
        # A container dialing across a uid map needs write permission on the socket
        # inode itself (measured: the default 0755 answers EACCES to another uid).
        sock.chmod(0o666)
    srv.listen(BACKLOG)
    while True:
        conn, _ = srv.accept()
        try:
            up = _dial_unix(target) if mode == "tcp2unix" else _dial_tcp(target)
        except OSError:
            conn.close()
            continue
        threading.Thread(target=pipe, args=(conn, up), daemon=True).start()
        threading.Thread(target=pipe, args=(up, conn), daemon=True).start()


if __name__ == "__main__":
    main()
