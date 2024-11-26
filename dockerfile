FROM python:3.11-slim

WORKDIR /python-docker

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 80

# Run your services first and then start the Flask server
CMD python -m DataAccessLayer.services.locationsServices && \
    python -m DataAccessLayer.services.positionServices && \
    python -m flask_app run --host=0.0.0.0 --port=80