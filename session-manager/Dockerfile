FROM python:3.7.4

ENV USER user
ENV HOME /home/${USER}

RUN groupadd -g 1000 ${USER} && \
    useradd -s /bin/false -g 1000 -u 1000 -d ${HOME} -m ${USER}

USER ${USER}
WORKDIR ${HOME}

COPY --chown=${USER}:${USER} session_manager.py ${HOME}/
CMD ["python", "session_manager.py"]