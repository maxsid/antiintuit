FROM python:3.7.4

ENV USER user
ENV HOME /home/${USER}
ENV PYTHONPATH ${HOME}

RUN groupadd -g 1000 ${USER} && \
    useradd -s /bin/false -g 1000 -u 1000 -Nmd ${HOME} ${USER}

USER ${USER}
WORKDIR ${HOME}