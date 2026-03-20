#!/bin/bash
# SSL Certificate Setup Script for TonyBot VPS Deployment
# Domains: skyfxbot.spotbox.online & apiskyfxbot.spotbox.online

set -e

PROJECT_DIR="/root/TonyBot/ERICKsky-signal-engine"
SSL_DIR="$PROJECT_DIR/nginx/ssl"

echo "======================================"
echo "  SSL Certificate Setup"
echo "======================================"
echo ""

# Create SSL directory
mkdir -p "$SSL_DIR"

echo "Option 1: Using Let's Encrypt (Recommended for production)"
echo "-----------------------------------------------------------"
echo "1. Install certbot:"
echo "   apt-get update && apt-get install -y certbot"
echo ""
echo "2. Obtain certificates:"
echo "   certbot certonly --standalone -d skyfxbot.spotbox.online -d apiskyfxbot.spotbox.online"
echo ""
echo "3. Copy certificates to project:"
echo "   cp /etc/letsencrypt/live/skyfxbot.spotbox.online/fullchain.pem $SSL_DIR/skyfxbot.crt"
echo "   cp /etc/letsencrypt/live/skyfxbot.spotbox.online/privkey.pem $SSL_DIR/skyfxbot.key"
echo "   cp /etc/letsencrypt/live/apiskyfxbot.spotbox.online/fullchain.pem $SSL_DIR/apiskyfxbot.crt"
echo "   cp /etc/letsencrypt/live/apiskyfxbot.spotbox.online/privkey.pem $SSL_DIR/apiskyfxbot.key"
echo ""
echo "4. Setup auto-renewal:"
echo "   echo '0 0 * * * root certbot renew --quiet' | sudo tee -a /etc/crontab"
echo ""

echo "Option 2: Using Self-Signed Certificates (For testing only)"
echo "-----------------------------------------------------------"
read -p "Generate self-signed certificates? (y/n): " answer

if [ "$answer" = "y" ]; then
    echo "Generating self-signed certificates..."

    # Generate for skyfxbot.spotbox.online
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/skyfxbot.key" \
        -out "$SSL_DIR/skyfxbot.crt" \
        -subj "/CN=skyfxbot.spotbox.online" \
        -addext "subjectAltName=DNS:skyfxbot.spotbox.online"

    # Generate for apiskyfxbot.spotbox.online
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/apiskyfxbot.key" \
        -out "$SSL_DIR/apiskyfxbot.crt" \
        -subj "/CN=apiskyfxbot.spotbox.online" \
        -addext "subjectAltName=DNS:apiskyfxbot.spotbox.online"

    echo "✓ Self-signed certificates generated!"
    echo "  Location: $SSL_DIR"
    ls -la "$SSL_DIR"
else
    echo "Skipping certificate generation."
    echo "Please manually place your certificates in: $SSL_DIR"
    echo "  - skyfxbot.crt / skyfxbot.key (for dashboard)"
    echo "  - apiskyfxbot.crt / apiskyfxbot.key (for API)"
fi

echo ""
echo "======================================"
echo "  Next Steps"
echo "======================================"
echo "1. Ensure DNS A records point to your VPS IP:"
echo "   - skyfxbot.spotbox.online -> YOUR_VPS_IP"
echo "   - apiskyfxbot.spotbox.online -> YOUR_VPS_IP"
echo ""
echo "2. Deploy the application:"
echo "   cd $PROJECT_DIR"
echo "   docker-compose up -d --build"
echo ""
echo "3. Check logs:"
echo "   docker-compose logs -f"
echo ""
