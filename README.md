# Tao of Founders - Backend API

Backend Flask pour l'application de traitement de PDFs et génération de contenu IA.

## 🚀 Installation Rapide

### 1. Créer l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate  # Sur macOS/Linux
# ou
venv\Scripts\activate  # Sur Windows
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Configurer les variables d'environnement

Copiez le fichier `.env.example` en `.env` et ajoutez vos clés API :

```bash
cp .env.example .env
```

Éditez `.env` avec vos clés :

```env
# API Keys Configuration
LLAMA_CLOUD_API_KEY=your_llama_cloud_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Qdrant Cloud Configuration (optionnel, sinon utilise le stockage local)
QDRANT_URL=your_qdrant_cloud_url_here
QDRANT_API_KEY=your_qdrant_api_key_here
```

### 4. Lancer le serveur

```bash
python app.py
```

Le serveur démarre sur **http://localhost:8080**

## 📁 Structure du projet

```
backend/
├── app.py              # Application Flask principale
├── requirements.txt    # Dépendances Python
├── .env               # Configuration (à créer)
├── .env.example       # Template de configuration
├── uploads/           # Dossier des PDFs uploadés
├── outputs/           # Dossier des fichiers générés
└── qdrant_storage/    # Stockage local Qdrant (si pas de cloud)
```

## 🔌 Endpoints API

### Upload & Processing

- **POST /upload** - Upload un PDF
- **GET /status/{job_id}** - Vérifier le statut de conversion
- **POST /auto-pipeline/{job_id}** - Générer les embeddings et injecter dans Qdrant

### Content Generation

- **POST /generate-content** - Générer du contenu IA à partir de la base de connaissances
  ```json
  {
    "keywords": "entrepreneurship",
    "instructions": "Extract key quotes",
    "num_chunks": 10
  }
  ```

### Database

- **GET /api/database/stats** - Statistiques de la base de données
- **GET /api/database/documents** - Liste des documents (avec pagination)
- **GET /api/database/documents/list** - Liste complète des documents uniques (scalable)
  - Query params: `search` (optionnel) pour filtrer par nom

## ⚙️ Configuration

### Base de données vectorielle

**Option 1 : Qdrant Cloud (recommandé)**
- Définissez `QDRANT_URL` et `QDRANT_API_KEY` dans `.env`
- Les données sont stockées dans le cloud

**Option 2 : Qdrant Local**
- Ne définissez pas les variables Qdrant dans `.env`
- Les données sont stockées dans `./qdrant_storage/`

### Modèles IA

- **OpenAI** : Pour les embeddings (text-embedding-3-small)
- **Anthropic Claude** : Pour la génération de contenu
- **LlamaParse** : Backup pour l'extraction de texte des PDFs complexes

## 🧪 Test rapide

```bash
# Vérifier que le serveur fonctionne
curl http://localhost:8080/api/database/stats
```

## 📝 Notes

- **Port** : 8080 par défaut
- **Debug mode** : Activé par défaut (désactiver en production)
- **CORS** : Configuré pour permettre toutes les origines (ajuster en production)
- **Timeouts** : Les timeouts sont configurés pour les opérations longues (conversion PDF, génération embeddings)

## 🔧 Dépannage

### Erreur "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### Erreur "Port already in use"
```bash
# Changer le port dans app.py, ligne finale :
app.run(host='0.0.0.0', port=8081, debug=True)
```

### Erreur API Keys
- Vérifiez que toutes les clés API sont valides dans `.env`
- Redémarrez le serveur après modification de `.env`

## 🚀 Production

Pour la production, utilisez un serveur WSGI comme **Gunicorn** :

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

Ou avec **Waitress** (compatible Windows) :

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=8080 app:app
```

## 📊 Monitoring

Les logs s'affichent dans la console avec des emojis pour faciliter le suivi :
- 🔍 = Recherche/Requête
- ✓ = Succès
- ❌ = Erreur
- 📚 = Base de données
- 🎯 = Configuration

## 🔐 Sécurité

Pour la production :
1. Désactivez le mode debug : `debug=False`
2. Configurez CORS correctement
3. Utilisez HTTPS
4. Protégez vos clés API avec des variables d'environnement
5. Ajoutez une authentification si nécessaire
