FROM python:3.11-slim

COPY . /app

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

COPY .env /app/.env

EXPOSE 8501

RUN mkdir ~/.streamlit

COPY .streamlit/config.toml /root/.streamlit/config.toml


ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
CMD [ "app.py" ]