FROM maxsid/antiintuit:latest

RUN pip install flask --user  --no-warn-script-location

CMD ["python", "-c", "from antiintuit.api import run_server; run_server()"]