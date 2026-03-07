#!/bin/bash
# Generate self-signed SSL certificate for localhost development
set -e

CERT_DIR="$(cd "$(dirname "$0")/ssl" && pwd)"
mkdir -p "$CERT_DIR"

echo "Generating self-signed certificate in $CERT_DIR ..."

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/localhost.key" \
  -out "$CERT_DIR/localhost.crt" \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=ContractAI/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Certificate generated:"
echo "  $CERT_DIR/localhost.crt"
echo "  $CERT_DIR/localhost.key"
echo ""
echo "On macOS, trust the cert to avoid browser warnings:"
echo "  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_DIR/localhost.crt"
