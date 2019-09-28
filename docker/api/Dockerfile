FROM maxsid/antiintuit

USER root
RUN pip install flask
USER ${USER}

CMD ["python", "-c", "from antiintuit.api import run_server; run_server()"]