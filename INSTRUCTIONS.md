# 📖 Instructions complètes - Tao Bite Backend

Guide complet pour installer, lancer et utiliser l'API backend.

---

## 🚀 Installation et Lancement

### Prérequis
- Python 3.9+
- pip3
- git

### Étape 1 : Cloner le repository

```bash
git clone https://github.com/yasser-ensembl3/tao-bite-backend.git
cd tao-bite-backend
```

### Étape 2 : Créer un environnement virtuel (recommandé)

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python3 -m venv venv
venv\Scripts\activate
```

### Étape 3 : Installer les dépendances

```bash
pip install -r requirements.txt
```

### Étape 4 : Configurer les clés API

Créez un fichier `.env` à la racine du projet :

```bash
cp .env.example .env
```

Éditez le fichier `.env` avec vos clés API :

```env
# API Keys Configuration
LLAMA_CLOUD_API_KEY=votre_cle_llama_cloud
OPENAI_API_KEY=votre_cle_openai
ANTHROPIC_API_KEY=votre_cle_anthropic

# Qdrant Cloud Configuration (optionnel)
QDRANT_URL=votre_url_qdrant_cloud
QDRANT_API_KEY=votre_cle_qdrant
```

### Étape 5 : Lancer le serveur

```bash
python3 app.py
```

Le serveur démarre sur **http://localhost:8080**

---

## 📚 Utilisation de l'API

### Workflow complet

#### 1️⃣ Uploader un PDF

**Commande :**
```bash
curl -X POST http://localhost:8080/upload \
  -F "file=@chemin/vers/votre-document.pdf"
```

**Exemple avec un fichier test :**
```bash
curl -X POST http://localhost:8080/upload \
  -F "file=@test.pdf"
```

**Réponse attendue :**
```json
{
  "success": true,
  "message": "File uploaded successfully",
  "job_id": "abc123-def456-789ghi",
  "filename": "test.pdf"
}
```

**💡 Important :** Notez le `job_id` - vous en aurez besoin pour les étapes suivantes !

---

#### 2️⃣ Vérifier le statut de conversion

**Commande :**
```bash
curl http://localhost:8080/status/VOTRE_JOB_ID
```

**Exemple :**
```bash
curl http://localhost:8080/status/abc123-def456-789ghi
```

**Réponse (en cours) :**
```json
{
  "status": "processing",
  "message": "Converting PDF...",
  "job_id": "abc123-def456-789ghi"
}
```

**Réponse (terminée) :**
```json
{
  "status": "completed",
  "message": "Conversion complete",
  "job_id": "abc123-def456-789ghi",
  "markdown_file": "outputs/abc123-def456-789ghi.md"
}
```

**💡 Astuce :** Attendez que le statut soit "completed" avant de passer à l'étape suivante.

---

#### 3️⃣ Télécharger le markdown (optionnel)

**Commande :**
```bash
curl http://localhost:8080/download/VOTRE_JOB_ID -o document.md
```

**Exemple :**
```bash
curl http://localhost:8080/download/abc123-def456-789ghi -o mon-document.md
```

---

#### 4️⃣ Chunking + Embeddings + Injection dans la base vectorielle

Cette commande fait tout automatiquement :
- Découpe le texte en chunks
- Génère les embeddings avec OpenAI
- Injecte dans Qdrant

**Commande :**
```bash
curl -X POST http://localhost:8080/auto-pipeline/VOTRE_JOB_ID \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "collection_name": "pdf_documents"
  }'
```

**Exemple :**
```bash
curl -X POST http://localhost:8080/auto-pipeline/abc123-def456-789ghi \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "collection_name": "pdf_documents"
  }'
```

**Paramètres :**
- `chunk_size` : Taille de chaque chunk en tokens (recommandé: 1000)
- `chunk_overlap` : Chevauchement entre chunks (recommandé: 200)
- `collection_name` : Nom de la collection Qdrant (défaut: "pdf_documents")

**Réponse attendue :**
```json
{
  "success": true,
  "message": "Pipeline completed successfully",
  "total_chunks": 145,
  "total_tokens": 98432,
  "collection_name": "pdf_documents"
}
```

---

#### 5️⃣ Générer du contenu avec Claude AI

Recherchez sémantiquement dans vos documents et générez du contenu avec Claude.

**Commande :**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "vos mots-clés",
    "instructions": "ce que vous voulez générer",
    "num_chunks": 10,
    "min_relevance": 0.3
  }'
```

**Exemples pratiques :**

**Exemple 1 : Extraire des citations**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "entrepreneurship leadership",
    "instructions": "Extraire les 5 meilleures citations avec les noms des auteurs",
    "num_chunks": 10
  }'
```

**Exemple 2 : Résumer des concepts**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "innovation startup",
    "instructions": "Résumer les concepts clés en 5 points principaux",
    "num_chunks": 15
  }'
```

**Exemple 3 : Créer un article**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "decision making psychology",
    "instructions": "Créer un article de blog de 500 mots sur ce sujet",
    "num_chunks": 20
  }'
```

**Paramètres :**
- `keywords` (obligatoire) : Mots-clés pour la recherche sémantique
- `instructions` (obligatoire) : Instructions pour Claude AI
- `num_chunks` (optionnel) : Nombre de passages pertinents à utiliser (défaut: 10)
- `min_relevance` (optionnel) : Score minimum de pertinence 0-1 (défaut: 0.3)

**Réponse :**
```json
{
  "success": true,
  "content": "Le contenu généré par Claude...",
  "metadata": {
    "chunks_found": 10,
    "avg_relevance": 0.72,
    "max_relevance": 0.89,
    "processing_time": 2.34
  }
}
```

---

## 📊 Consulter la base de données

### Voir les statistiques de la base

```bash
curl http://localhost:8080/api/database/stats
```

**Réponse :**
```json
{
  "collections": [
    {
      "name": "pdf_documents",
      "vectors_count": 2335,
      "vector_size": 1536
    }
  ],
  "total_vectors": 2335
}
```

---

### Lister tous les documents

```bash
curl http://localhost:8080/api/database/documents/list
```

**Réponse :**
```json
{
  "collection_name": "pdf_documents",
  "documents": [
    {
      "filename": "Thinking Fast and Slow.pdf",
      "chunk_count": 410,
      "total_tokens": 265038,
      "source": "pdfplumber",
      "job_id": "abc123"
    },
    {
      "filename": "Zero to One.pdf",
      "chunk_count": 285,
      "total_tokens": 189432,
      "source": "llamaparse",
      "job_id": "def456"
    }
  ],
  "total_documents": 2,
  "total_chunks": 695
}
```

---

### Rechercher un document spécifique

```bash
curl "http://localhost:8080/api/database/documents/list?search=thinking"
```

---

### Voir les documents avec pagination

```bash
curl "http://localhost:8080/api/database/documents?limit=50&offset=0"
```

---

## 🔍 Recherche sémantique dans Qdrant

```bash
curl -X POST http://localhost:8080/qdrant/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "votre recherche",
    "collection_name": "pdf_documents",
    "limit": 10
  }'
```

---

## 🤖 Script automatisé complet

Créez un fichier `test-pipeline.sh` :

```bash
#!/bin/bash

# Configuration
PDF_FILE="mon-document.pdf"
COLLECTION="pdf_documents"

echo "=========================================="
echo "🚀 PIPELINE COMPLET TAO BITE BACKEND"
echo "=========================================="

# 1. Upload
echo ""
echo "📤 Étape 1/5 : Upload du PDF..."
RESPONSE=$(curl -s -X POST http://localhost:8080/upload -F "file=@$PDF_FILE")
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

if [ "$JOB_ID" == "null" ]; then
  echo "❌ Erreur lors de l'upload"
  echo $RESPONSE | jq '.'
  exit 1
fi

echo "✅ Upload réussi - Job ID: $JOB_ID"

# 2. Attendre la conversion
echo ""
echo "⏳ Étape 2/5 : Conversion en cours..."
while true; do
  STATUS=$(curl -s http://localhost:8080/status/$JOB_ID | jq -r '.status')

  if [ "$STATUS" == "completed" ]; then
    echo "✅ Conversion terminée!"
    break
  elif [ "$STATUS" == "error" ]; then
    echo "❌ Erreur lors de la conversion"
    exit 1
  fi

  echo "   Status: $STATUS - attente..."
  sleep 2
done

# 3. Processing + Injection
echo ""
echo "🔄 Étape 3/5 : Chunking et injection dans Qdrant..."
PIPELINE_RESPONSE=$(curl -s -X POST http://localhost:8080/auto-pipeline/$JOB_ID \
  -H "Content-Type: application/json" \
  -d "{
    \"chunk_size\": 1000,
    \"chunk_overlap\": 200,
    \"collection_name\": \"$COLLECTION\"
  }")

TOTAL_CHUNKS=$(echo $PIPELINE_RESPONSE | jq -r '.total_chunks')
echo "✅ Pipeline terminé - $TOTAL_CHUNKS chunks créés"

# 4. Stats
echo ""
echo "📊 Étape 4/5 : Statistiques de la base..."
curl -s http://localhost:8080/api/database/stats | jq '.'

# 5. Génération de contenu
echo ""
echo "🤖 Étape 5/5 : Génération de contenu IA..."
CONTENT=$(curl -s -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "innovation startup entrepreneurship",
    "instructions": "Résumer les concepts clés en 3 points principaux",
    "num_chunks": 10
  }')

echo ""
echo "=========================================="
echo "✅ CONTENU GÉNÉRÉ :"
echo "=========================================="
echo $CONTENT | jq -r '.content'
echo ""
echo "=========================================="
echo "📈 Métadonnées :"
echo "=========================================="
echo $CONTENT | jq '.metadata'

echo ""
echo "✅ Pipeline complet terminé avec succès!"
```

**Utilisation :**
```bash
chmod +x test-pipeline.sh
./test-pipeline.sh
```

**Note :** Ce script nécessite `jq` pour parser le JSON.
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

---

## 🛠️ Commandes utiles

### Arrêter le serveur
```bash
# Dans le terminal où le serveur tourne
Ctrl+C
```

### Redémarrer le serveur
```bash
python3 app.py
```

### Vérifier si le serveur fonctionne
```bash
curl http://localhost:8080/api/database/stats
```

### Nettoyer les uploads et outputs
```bash
rm -rf uploads/* outputs/*
```

### Voir les logs en temps réel
Les logs s'affichent directement dans le terminal avec des emojis :
- 🔍 = Recherche/Requête
- ✓ = Succès
- ❌ = Erreur
- 📚 = Base de données
- 🎯 = Configuration

---

## 🐛 Dépannage

### Le serveur ne démarre pas

**Erreur : Port 8080 déjà utilisé**
```bash
# Trouver le processus
lsof -ti:8080

# Tuer le processus
kill -9 $(lsof -ti:8080)
```

**Erreur : Module manquant**
```bash
pip install -r requirements.txt
```

---

### Les clés API ne fonctionnent pas

1. Vérifiez que le fichier `.env` existe
2. Vérifiez que les clés sont correctes (sans espaces)
3. Redémarrez le serveur après modification du `.env`

---

### La conversion échoue

Le système a 2 méthodes de fallback :
1. **pdfplumber** (rapide, pour PDFs simples)
2. **LlamaParse** (backup, pour PDFs complexes)

Si les deux échouent, vérifiez :
- Le PDF n'est pas corrompu
- Le PDF n'est pas protégé par mot de passe
- Votre clé `LLAMA_CLOUD_API_KEY` est valide

---

### Qdrant ne fonctionne pas

**Option 1 : Utiliser Qdrant local**
- Ne définissez pas `QDRANT_URL` et `QDRANT_API_KEY` dans `.env`
- Les données seront stockées dans `./qdrant_storage/`

**Option 2 : Utiliser Qdrant Cloud**
- Vérifiez que `QDRANT_URL` et `QDRANT_API_KEY` sont corrects
- Format URL : `https://xxx.cloud.qdrant.io`

---

## 📖 Ressources

- **API complète** : Voir `API.md`
- **Guide rapide** : Voir `QUICKSTART.md`
- **README** : Voir `README.md`
- **GitHub** : https://github.com/yasser-ensembl3/tao-bite-backend

---

## 💡 Exemples d'utilisation

### Cas d'usage 1 : Bibliothèque de livres

Upload plusieurs livres et posez des questions cross-documents :

```bash
# Upload livre 1
curl -X POST http://localhost:8080/upload -F "file=@livre1.pdf"
# Attendez conversion + auto-pipeline

# Upload livre 2
curl -X POST http://localhost:8080/upload -F "file=@livre2.pdf"
# Attendez conversion + auto-pipeline

# Recherche cross-documents
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "leadership resilience",
    "instructions": "Comparer les perspectives des différents auteurs sur ce sujet",
    "num_chunks": 20
  }'
```

---

### Cas d'usage 2 : Extraction de citations

```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "failure success pivot",
    "instructions": "Extraire 10 citations inspirantes sur l'\''échec et le pivot, avec nom de l'\''auteur et contexte",
    "num_chunks": 15
  }'
```

---

### Cas d'usage 3 : Génération de contenu Substack

```bash
curl -X POST http://localhost:8080/generate-draft \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "The Art of Decision Making",
    "num_chunks": 20,
    "style": "conversational"
  }'
```

---

## 🔐 Sécurité (Production)

Si vous déployez en production :

1. **Désactivez le mode debug** dans `app.py`
   ```python
   app.run(host='0.0.0.0', port=8080, debug=False)
   ```

2. **Utilisez un serveur WSGI** (Gunicorn ou Waitress)
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8080 app:app
   ```

3. **Configurez CORS** pour votre domaine uniquement

4. **Utilisez HTTPS** (nginx + Let's Encrypt)

5. **Ajoutez une authentification** (JWT, API keys, etc.)

6. **Rate limiting** (Flask-Limiter ou nginx)

---

## ✅ Checklist avant de commencer

- [ ] Python 3.9+ installé
- [ ] pip installé
- [ ] Repository cloné
- [ ] Dépendances installées
- [ ] Fichier `.env` créé avec les clés API
- [ ] Serveur lancé et accessible sur http://localhost:8080
- [ ] Test de base réussi (`curl http://localhost:8080/api/database/stats`)

---

**Vous êtes prêt à utiliser Tao Bite Backend ! 🚀**
