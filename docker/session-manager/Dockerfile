FROM maxsid/antiintuit:core

RUN pip install ujson --user --no-warn-script-location
COPY --chown=${USER}:${USER} session_manager.py ${HOME}/
CMD ["python", "session_manager.py"]