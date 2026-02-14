#!/bin/bash
# GCP VM setup for WoundChrono
# Usage: bash deployment/gcp_setup.sh

set -euo pipefail

PROJECT_ID="oralya"
ZONE="us-central1-a"
INSTANCE_NAME="woundchrono-gpu"
MACHINE_TYPE="n1-standard-4"
GPU_TYPE="nvidia-tesla-t4"
BOOT_DISK_SIZE="100GB"

echo "=== WoundChrono GCP Setup ==="
echo "Project: $PROJECT_ID"
echo "Zone: $ZONE"

# Set project
gcloud config set project "$PROJECT_ID"

# Create VM with T4 GPU (spot pricing)
echo "Creating GPU VM..."
gcloud compute instances create "$INSTANCE_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --accelerator="type=$GPU_TYPE,count=1" \
  --image-family="pytorch-latest-gpu" \
  --image-project="deeplearning-platform-release" \
  --boot-disk-size="$BOOT_DISK_SIZE" \
  --boot-disk-type="pd-ssd" \
  --maintenance-policy="TERMINATE" \
  --provisioning-model="SPOT" \
  --metadata="install-nvidia-driver=True" \
  --tags="http-server,https-server"

# Allow HTTP/HTTPS traffic
echo "Configuring firewall..."
gcloud compute firewall-rules create allow-woundchrono \
  --allow tcp:3000,tcp:8000 \
  --target-tags http-server \
  --description "Allow WoundChrono ports" \
  2>/dev/null || echo "Firewall rule already exists."

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
  --zone="$ZONE" \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "=== VM Created ==="
echo "Instance: $INSTANCE_NAME"
echo "External IP: $EXTERNAL_IP"
echo "SSH: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo ""
echo "=== Next Steps ==="
echo "1. SSH into the VM"
echo "2. Clone the repo"
echo "3. Run: docker compose up --build"
echo "4. Access: http://$EXTERNAL_IP:3000"
