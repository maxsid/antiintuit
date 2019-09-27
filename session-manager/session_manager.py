import logging
import socketserver
from os import environ
from sys import stdout

import ujson


class SessionManagerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global sessions, logger
        self.data = self.request.recv(68).strip()
        if self.data == b"healthz" or len(self.data) == 0:
            logger.debug("Health check from %s.", self.client_address[0])
            self.request.sendall(bytes(True))
            return
        logger.debug("%s wrote: %s", self.client_address[0], repr(self.data))
        assert len(self.data) == 68, "Incorrect data ({}) length".format(repr(self.data))
        assert self.data[:4] in (b"CHK:", b"DEL:"), "Incorrect operation"
        operation, session = self.data[:4], self.data[4:]
        if operation == b"CHK:":
            response_data = dict({"new": False, "allow": False, "pos": 0})
            if session not in sessions:
                sessions.append(session)
                response_data["new"] = True
            if sessions[0] == session:
                response_data["allow"] = True
            else:
                response_data["pos"] = sessions.index(session)
        else:
            assert session in sessions, "The order hasn't this session."
            assert sessions[0] == session, "This session isn't the first in the order."
            sessions.pop(0)
            response_data = True
        logger.info("%s (%s) will response data: %s", self.client_address[0], session, ujson.dumps(response_data))
        self.request.sendall(bytes(ujson.dumps(response_data), "utf-8"))


if __name__ == "__main__":
    logger = logging.getLogger("antiintuit.session_manager")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(stdout))

    HOST = environ.get("HOST", "")
    PORT = int(environ.get("PORT", 26960))
    sessions = list()
    logger.debug("Server will be started with listening '%s:%i'.", HOST, PORT)
    with socketserver.TCPServer((HOST, PORT), SessionManagerHandler) as server:
        server.serve_forever()
