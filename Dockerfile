# Image officielle Python 3.11 légère
FROM python:3.11-slim

# Crée un dossier de travail dans le conteneur
WORKDIR /app

# Copie le fichier requirements.txt dans le conteneur
COPY requirements.txt .
# Installe les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt
# Copie tout le code dans le conteneur
COPY . .

# Expose le port 8000 pour le serveur Django
EXPOSE 8000

# Commande pour lancer le serveur Django
CMD ["gunicorn", "pharma.wsgi:application", "--bind", "0.0.0.0:8000"]
