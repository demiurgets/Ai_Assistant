```powershell
# Build image
docker build -t <image-name> .

# Run container locally for testing 
docker run -p <port:port> <image-name>
# Example
docker run -p 80:80 flask_ai2

# Push container
az login

az acr login --name <container-registry-name>
# Example
az acr login --name qondacr


docker tag <image-name> < <login server> /samples/ <image-name:tag version> >
# Example
docker tag flask_ai2 qondacr.azurecr.io/samples/flask_ai2:latest 


docker push < <login server> /samples/ <image-name:tag version> >
# Example
docker push qondacr.azurecr.io/samples/flask_ai2:latest 

end