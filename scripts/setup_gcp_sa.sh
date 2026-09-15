#!/usr/bin/env bash
# ==============================================================================
# Setup Service Account per Deploy Automatico con GitHub Actions su Cloud Run
# ==============================================================================
# Questo script va eseguito nella Google Cloud Shell (o sul terminale dove gcloud è configurato).
# Crea un Service Account dedicato, assegna i permessi minimi necessari ed esporta la chiave JSON.

set -e

echo "🚀 Avvio configurazione Service Account per GitHub Actions..."

# 1. Recupera o verifica il Project ID corrente (da argomento, config o input utente)
PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "⚠️ Nessun progetto selezionato. Inserisci il tuo Project ID di Google Cloud:"
  if [ -t 0 ]; then
    read -r PROJECT_ID
  elif [ -e /dev/tty ]; then
    read -r PROJECT_ID < /dev/tty
  fi
  if [ -z "$PROJECT_ID" ]; then
    echo "❌ Errore: Project ID non fornito."
    exit 1
  fi
  gcloud config set project "$PROJECT_ID"
fi

echo "📌 Google Cloud Project ID: $PROJECT_ID"

# 2. Abilita le API necessarie
echo "⏳ Abilitazione delle API di Google Cloud richieste (Cloud Run, Cloud Build, Artifact Registry, IAM)..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com

SA_NAME="github-actions-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 3. Crea il Service Account se non esiste già
if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  echo "👤 Creazione Service Account '$SA_NAME'..."
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="GitHub Actions Deployer" \
    --description="Service account per deploy CI/CD da GitHub Actions a Cloud Run"
else
  echo "ℹ️ Il Service Account '$SA_NAME' esiste già."
fi

# 4. Assegna i ruoli necessari
ROLES=(
  "roles/run.admin"
  "roles/cloudbuild.builds.editor"
  "roles/storage.admin"
  "roles/artifactregistry.admin"
  "roles/iam.serviceAccountUser"
)

echo "🔑 Assegnazione ruoli IAM al Service Account..."
for ROLE in "${ROLES[@]}"; do
  echo "   -> Aggiunta del ruolo $ROLE..."
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" \
    --condition=None >/dev/null
done

# 5. Genera la chiave JSON
KEY_FILE="gcp-key.json"
echo "🔐 Generazione della chiave JSON..."
gcloud iam service-accounts keys create "$KEY_FILE" \
  --iam-account="$SA_EMAIL"

echo ""
echo "=============================================================================="
echo "🎉 CONFIGURAZIONE COMPLETATA CON SUCCESSO!"
echo "=============================================================================="
echo ""
echo "Ora aggiungi i seguenti 2 Secret nel tuo repository GitHub:"
echo "👉 Vai su: https://github.com/giorgioascoli-bit/api-album-detail/settings/secrets/actions"
echo ""
echo "1️⃣ Secret Name: GCP_PROJECT_ID"
echo "   Secret Value: $PROJECT_ID"
echo ""
echo "2️⃣ Secret Name: GCP_SA_KEY"
echo "   Secret Value (copia l'intero blocco JSON qui sotto):"
echo "------------------------------------------------------------------------------"
cat "$KEY_FILE"
echo ""
echo "------------------------------------------------------------------------------"
echo "✅ Fatto! Ad ogni push sul ramo 'main', GitHub testerà e pubblicherà la tua API!"
echo "=============================================================================="
