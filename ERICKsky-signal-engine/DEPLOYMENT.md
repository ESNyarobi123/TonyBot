# TonyBot VPS Deployment Guide

## Production URLs
- **Dashboard**: https://skyfxbot.spotbox.online
- **API Backend**: https://apiskyfxbot.spotbox.online

---

## Prerequisites
- VPS with Docker & Docker Compose installed
- DNS A records pointing to VPS IP:
  - `skyfxbot.spotbox.online`
  - `apiskyfxbot.spotbox.online`
- Ports 80 and 443 open on firewall

---

## Step 1: Clone Project
```bash
cd /root
git clone https://github.com/ESNyarobi123/TonyBot.git
cd TonyBot/ERICKsky-signal-engine
```

## Step 2: Configure Environment

### Root .env (Database Password)
```bash
# Already configured:
DB_PASSWORD=ERICKskyBot2025
```

### Signal Bot .env
Check `/root/TonyBot/ERICKsky-signal-engine/signal-bot/.env`:
- Update `TWELVE_DATA_API_KEY` with your API key
- Update `TELEGRAM_BOT_TOKEN` with your bot token
- Update `TELEGRAM_FREE_CHANNEL` and `TELEGRAM_PREMIUM_CHANNEL` with channel IDs

### Dashboard .env
Already updated with production URLs:
- `APP_URL=https://skyfxbot.spotbox.online`
- `REVERB_HOST=skyfxbot.spotbox.online`

---

## Step 3: Setup SSL Certificates

### Option A: Let's Encrypt (Production)
```bash
# Install certbot
apt-get update && apt-get install -y certbot

# Obtain certificates
certbot certonly --standalone \
  -d skyfxbot.spotbox.online \
  -d apiskyfxbot.spotbox.online

# Copy to project
mkdir -p nginx/ssl
cp /etc/letsencrypt/live/skyfxbot.spotbox.online/fullchain.pem nginx/ssl/skyfxbot.crt
cp /etc/letsencrypt/live/skyfxbot.spotbox.online/privkey.pem nginx/ssl/skyfxbot.key
cp /etc/letsencrypt/live/apiskyfxbot.spotbox.online/fullchain.pem nginx/ssl/apiskyfxbot.crt
cp /etc/letsencrypt/live/apiskyfxbot.spotbox.online/privkey.pem nginx/ssl/apiskyfxbot.key
```

### Option B: Self-Signed (Testing)
```bash
chmod +x setup-ssl.sh
./setup-ssl.sh
```

---

## Step 4: Deploy Application

```bash
docker-compose up -d --build
```

This starts:
- `erickskybot-engine` - Main signal bot scheduler
- `erickskybot-api` - API server (port 8000)
- `erickskybot-celery` - Celery workers
- `erickskybot-beat` - Celery beat scheduler
- `erickskybot-dashboard` - Laravel dashboard
- `erickskybot-postgres` - PostgreSQL database
- `erickskybot-redis` - Redis cache
- `erickskybot-nginx` - Nginx reverse proxy (ports 80/443)

---

## Step 5: Verify Deployment

### Check all services are running:
```bash
docker-compose ps
```

### View logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f dashboard
docker-compose logs -f signal-bot
docker-compose logs -f signal-bot-api
```

### Test endpoints:
```bash
# Dashboard
curl https://skyfxbot.spotbox.online/health

# API
curl https://apiskyfxbot.spotbox.online/health
curl https://apiskyfxbot.spotbox.online/api/v1/status
```

---

## Step 6: Laravel Setup (First Time)

```bash
# Run migrations
docker-compose exec dashboard php artisan migrate --force

# Clear and cache config
docker-compose exec dashboard php artisan config:cache
docker-compose exec dashboard php artisan route:cache
docker-compose exec dashboard php artisan view:cache
```

---

## Useful Commands

### Restart services:
```bash
docker-compose restart nginx
docker-compose restart signal-bot
docker-compose restart dashboard
```

### Update code and rebuild:
```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Database backup:
```bash
docker-compose exec postgres pg_dump -U erickskybot erickskybot > backup.sql
```

### Access containers:
```bash
docker-compose exec dashboard bash
docker-compose exec signal-bot bash
docker-compose exec postgres psql -U erickskybot -d erickskybot
```

---

## Troubleshooting

### 502 Bad Gateway
- Check if containers are running: `docker-compose ps`
- Check logs: `docker-compose logs <service>`

### SSL Certificate Errors
- Verify certificates exist in `nginx/ssl/`
- Check certificate paths in `nginx/default.conf`
- Ensure domain names match certificates

### Database Connection Issues
- Verify postgres container is healthy: `docker-compose ps`
- Check DB credentials in `.env` files

---

## Security Notes

1. **Change default passwords** in all `.env` files before production
2. **Secure your VPS** with firewall rules (only allow 80, 443, SSH)
3. **Keep Docker images updated** regularly
4. **Backup database** periodically
5. **Monitor logs** for suspicious activity
